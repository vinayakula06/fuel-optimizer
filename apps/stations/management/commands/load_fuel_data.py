import csv
import os
import urllib.request
import logging
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from django.utils import timezone
from apps.stations.models import FuelStation
from apps.routing.geocoder import NominatimGeocoder

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Loads fuel station data from a CSV file into the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            required=True,
            help="Path to the fuel prices CSV file",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and validate data without saving to the database",
        )

    def handle(self, *args, **options):
        csv_file_path = options["file"]
        dry_run = options["dry_run"]

        if not os.path.exists(csv_file_path):
            self.stderr.write(self.style.ERROR(f"File not found: {csv_file_path}"))
            return

        self.stdout.write(f"Parsing fuel data from: {csv_file_path}")

        # 1. Parse CSV and Deduplicate
        raw_rows = []
        try:
            with open(csv_file_path, mode="r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    raw_rows.append(row)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to read CSV: {e}"))
            return

        # Deduplicate: Group by OPIS Truckstop ID, keep lowest price
        # Keep only US states to avoid slow Nominatim geocoding for Canadian provinces
        US_STATES = {
            "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", 
            "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", 
            "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", 
            "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", 
            "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC"
        }
        deduped = {}
        dup_count = 0
        skipped_non_us = 0
        for row in raw_rows:
            try:
                opis_id = int(row["OPIS Truckstop ID"])
                price = float(row["Retail Price"])
                state = row.get("State", "").strip().upper()
                if state not in US_STATES:
                    skipped_non_us += 1
                    continue
            except (ValueError, TypeError, KeyError) as e:
                # Skip corrupt rows
                continue

            if opis_id in deduped:
                dup_count += 1
                if price < deduped[opis_id]["price"]:
                    deduped[opis_id] = {
                        "name": row.get("Truckstop Name", "").strip(),
                        "address": row.get("Address", "").strip(),
                        "city": row.get("City", "").strip(),
                        "state": state,
                        "rack_id": int(row["Rack ID"]) if row.get("Rack ID") else None,
                        "price": price,
                        "raw": row,
                    }
            else:
                deduped[opis_id] = {
                    "name": row.get("Truckstop Name", "").strip(),
                    "address": row.get("Address", "").strip(),
                    "city": row.get("City", "").strip(),
                    "state": state,
                    "rack_id": int(row["Rack ID"]) if row.get("Rack ID") else None,
                    "price": price,
                    "raw": row,
                }

        self.stdout.write(self.style.SUCCESS(
            f"Parsed {len(raw_rows)} rows. Unique US stations: {len(deduped)} (removed {dup_count} duplicates, skipped {skipped_non_us} non-US stations)."
        ))

        # 2. Set up Offline Geocoder Cache
        # Download us_cities.csv locally if not present to avoid rate limits
        local_cities_path = "us_cities.csv"
        if not os.path.exists(local_cities_path):
            self.stdout.write("Downloading offline cities database for high-speed geocoding...")
            try:
                url = "https://raw.githubusercontent.com/kelvins/US-Cities-Database/master/csv/us_cities.csv"
                urllib.request.urlretrieve(url, local_cities_path)
                self.stdout.write(self.style.SUCCESS("Offline cities database downloaded successfully."))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Failed to download offline database: {e}. Falling back to live API only."))

        offline_cities = {}
        if os.path.exists(local_cities_path):
            try:
                with open(local_cities_path, mode="r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        city_key = (row["CITY"].strip().lower(), row["STATE_CODE"].strip().upper())
                        offline_cities[city_key] = (float(row["LATITUDE"]), float(row["LONGITUDE"]))
                self.stdout.write(f"Loaded {len(offline_cities)} cities into offline geocoding cache.")
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Error loading offline cities: {e}"))

        # 3. Geocode unique city/state combinations
        # Extract all unique city-state combinations from the stations
        unique_city_states = {(info["city"].lower(), info["state"].upper()) for info in deduped.values()}
        self.stdout.write(f"Found {len(unique_city_states)} unique city/state pairs to geocode.")

        geocoded_cache = {}
        missing_count = 0
        
        # Geocode them
        for i, (city, state) in enumerate(unique_city_states, 1):
            if (city, state) in offline_cities:
                geocoded_cache[(city, state)] = offline_cities[(city, state)]
            else:
                # Fallback to live Nominatim API (with a sleep to respect rate limits)
                self.stdout.write(f"City '{city}, {state}' missing from offline DB. Querying Nominatim...")
                import time
                time.sleep(1.0)
                coords = NominatimGeocoder.geocode(city, state)
                if coords:
                    geocoded_cache[(city, state)] = coords
                else:
                    missing_count += 1
                    logger.warning(f"Could not geocode city: {city}, {state}")

        self.stdout.write(self.style.SUCCESS(
            f"Geocoding completed. Resolved: {len(geocoded_cache)} / {len(unique_city_states)} cities. Missing: {missing_count}."
        ))

        # 4. Construct FuelStation instances
        stations_to_create = []
        skipped_count = 0
        now = timezone.now()

        for opis_id, info in deduped.items():
            city_key = (info["city"].lower(), info["state"].upper())
            coords = geocoded_cache.get(city_key)
            if not coords:
                skipped_count += 1
                continue

            lat, lon = coords
            # Point takes (longitude, latitude) in GIS
            location = Point(lon, lat, srid=4326)

            station = FuelStation(
                opis_id=opis_id,
                name=info["name"],
                address=info["address"],
                city=info["city"],
                state=info["state"],
                rack_id=info["rack_id"],
                retail_price=info["price"],
                location=location,
                geocoded_at=now,
            )
            stations_to_create.append(station)

        self.stdout.write(f"Prepared {len(stations_to_create)} stations for database insertion (skipped {skipped_count} due to geocoding failures).")

        if dry_run:
            self.stdout.write(self.style.SUCCESS("Dry run active. Skipping database write."))
            return

        # 5. Bulk insert with conflict updates
        if stations_to_create:
            try:
                # unique_together = ('opis_id', 'retail_price')
                # If there is a conflict on opis_id and retail_price, update other fields.
                # Since we keep only the minimum retail price per opis_id, most inserts will be unique,
                # but if the price changes or we import new files, conflict handling ensures we keep
                # the DB clean.
                result = FuelStation.objects.bulk_create(
                    stations_to_create,
                    update_conflicts=True,
                    unique_fields=["opis_id", "retail_price"],
                    update_fields=["name", "address", "city", "state", "rack_id", "location", "geocoded_at"],
                )
                self.stdout.write(self.style.SUCCESS(
                    f"Successfully loaded/updated {len(result)} stations in the database."
                ))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Database bulk insert failed: {e}"))
                logger.error(f"Database bulk insert failed: {e}", exc_info=True)
        else:
            self.stdout.write("No stations were prepared for database insertion.")
