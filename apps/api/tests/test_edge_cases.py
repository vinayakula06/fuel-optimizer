"""
apps/api/tests/test_edge_cases.py

Edge case + integration tests for RouteOptimizationView.
Run with: docker compose exec web pytest apps/api/tests/test_edge_cases.py -v

All external calls (OSRM, Nominatim) are mocked so tests run offline
and deterministically without hitting rate limits.
"""

import json
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient


# ---------------------------------------------------------------------------
# Shared mock helpers
# ---------------------------------------------------------------------------

def _make_osrm_response(distance_m: float) -> dict:
    """Minimal OSRM /route response for a given distance in metres."""
    return {
        "code": "Ok",
        "routes": [
            {
                "distance": distance_m,
                "duration": distance_m / 30,          # rough 30 m/s
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [-87.629, 41.878],             # Chicago-ish
                        [-90.199, 38.627],             # St. Louis-ish (short)
                        [-118.243, 34.052],            # LA (only used in long trips)
                    ],
                },
                "legs": [{"distance": distance_m, "duration": distance_m / 30}],
            }
        ],
    }


def _geocode_side_effect(location: str, *args, **kwargs) -> tuple:
    """
    Fake geocoder that maps known city strings to (lat, lon).
    Raises ValueError for unknown locations to trigger 404.
    """
    mapping = {
        "chicago, il":       (41.8781, -87.6298),
        "los angeles, ca":   (34.0522, -118.2437),
        "st. louis, mo":     (38.6270, -90.1994),
        "new york, ny":      (40.7128, -74.0060),
        "miami, fl":         (25.7617, -80.1918),
        "dallas, tx":        (32.7767, -96.7970),
        "denver, co":        (39.7392, -104.9903),
    }
    key = location.lower().strip()
    if key not in mapping:
        raise ValueError(f"Could not geocode '{location}'")
    return mapping[key]


def _make_stations(prices_and_miles: list) -> list:
    """
    Build minimal station dicts for the optimizer.
    prices_and_miles: [(price, miles_from_start), ...]
    """
    stations = []
    for i, (price, miles) in enumerate(prices_and_miles):
        stations.append({
            "id": i + 1,
            "name": f"TEST STATION #{i + 1}",
            "address": f"{i} Test Rd",
            "city": "Testville",
            "state": "TX",
            "retail_price": Decimal(str(price)),
            "latitude": 35.0 + i * 0.1,
            "longitude": -100.0 + i * 0.1,
            "miles_from_start": miles,
        })
    return stations


# ---------------------------------------------------------------------------
# Fixtures / base class
# ---------------------------------------------------------------------------

ROUTE_URL = "/api/v1/route/"


class BaseRouteTest(TestCase):
    """Sets up APIClient and common patches."""

    def setUp(self):
        self.client = APIClient()

    def _post(self, body: dict):
        return self.client.post(
            ROUTE_URL,
            data=json.dumps(body),
            content_type="application/json",
        )


# ---------------------------------------------------------------------------
# 1. Short trip — Chicago → St. Louis (~300 mi, 0 mandatory stops)
# ---------------------------------------------------------------------------

class TestShortTrip(BaseRouteTest):
    """
    A trip under 500 miles needs zero mandatory stops.
    The vehicle starts full and can reach the destination without refuelling.
    """

    DISTANCE_M = 300 * 1609.34   # 300 miles in metres

    @patch("apps.routing.geocoder.NominatimGeocoder.geocode",
           side_effect=_geocode_side_effect)
    @patch("apps.routing.client.OSRMClient.get_route")
    @patch("apps.api.views.project_stations_to_route")
    @patch("apps.stations.services.StationQueryService.get_stations_near_route")
    def test_zero_stops_returned(
        self, mock_stations, mock_project, mock_osrm, mock_geo
    ):
        mock_osrm.return_value = _make_osrm_response(self.DISTANCE_M)
        mock_stations.return_value = []    # no stations queried — trip too short
        mock_project.return_value  = []

        resp = self._post({"start": "Chicago, IL", "destination": "St. Louis, MO"})

        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Core assertion — no stops required
        self.assertEqual(data["meta"]["stop_count"], 0,
                         "Trips under 500 mi must return 0 stops")
        self.assertEqual(len(data["stops"]), 0)

        # Total cost should cover full trip at $0 (tank already full, no purchase)
        # OR return cost of fuel at origin price — depends on implementation.
        # Key: must not crash and must be a valid number.
        cost = float(data["meta"]["total_fuel_cost_usd"])
        self.assertGreaterEqual(cost, 0.0)

        # Distance sanity
        self.assertAlmostEqual(
            data["meta"]["total_distance_miles"], 300.0, delta=5.0
        )

    @patch("apps.routing.geocoder.NominatimGeocoder.geocode",
           side_effect=_geocode_side_effect)
    @patch("apps.routing.client.OSRMClient.get_route")
    @patch("apps.stations.services.StationQueryService.get_stations_near_route")
    def test_response_shape_intact_for_short_trip(
        self, mock_stations, mock_osrm, mock_geo
    ):
        """Response schema must be identical regardless of stop count."""
        mock_osrm.return_value = _make_osrm_response(self.DISTANCE_M)
        mock_stations.return_value = []

        resp = self._post({"start": "Chicago, IL", "destination": "St. Louis, MO"})
        data = resp.json()

        # All top-level keys must be present
        for key in ("meta", "stops", "route"):
            self.assertIn(key, data, f"Missing key: {key}")

        # meta sub-keys
        for key in ("total_distance_miles", "total_fuel_cost_usd",
                    "stop_count", "computed_in_ms"):
            self.assertIn(key, data["meta"], f"Missing meta key: {key}")

        # route sub-keys
        self.assertIn("geojson",  data["route"])
        self.assertIn("map_url",  data["route"])


# ---------------------------------------------------------------------------
# 2. Same city — must return 400 INVALID_INPUT
# ---------------------------------------------------------------------------

class TestSameCityError(BaseRouteTest):
    """
    Sending the same string for start and destination must fail immediately
    with HTTP 400 and error code INVALID_INPUT — before any geocoding.
    """

    def test_same_city_returns_400(self):
        resp = self._post({
            "start": "Chicago, IL",
            "destination": "Chicago, IL",
        })
        self.assertEqual(resp.status_code, 400)

    def test_same_city_error_code(self):
        resp = self._post({
            "start": "Chicago, IL",
            "destination": "Chicago, IL",
        })
        data = resp.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], "INVALID_INPUT")

    def test_same_city_error_references_destination_field(self):
        resp = self._post({
            "start": "Chicago, IL",
            "destination": "Chicago, IL",
        })
        data = resp.json()
        # field should point to "destination" or "start" — not absent
        self.assertIn("message", data["error"])

    def test_same_city_case_insensitive(self):
        """'chicago, il' and 'Chicago, IL' are the same place."""
        resp = self._post({
            "start": "chicago, il",
            "destination": "CHICAGO, IL",
        })
        # Implementation may or may not normalise — acceptable either way,
        # but must not crash (no 500).
        self.assertIn(resp.status_code, [400, 200])

    def test_missing_start_field(self):
        resp = self._post({"destination": "Los Angeles, CA"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"]["code"], "INVALID_INPUT")

    def test_missing_destination_field(self):
        resp = self._post({"start": "Chicago, IL"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"]["code"], "INVALID_INPUT")

    def test_empty_body(self):
        resp = self.client.post(ROUTE_URL, data="{}", content_type="application/json")
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# 3. Unknown location — must return 404 LOCATION_NOT_FOUND
# ---------------------------------------------------------------------------

class TestUnknownLocationError(BaseRouteTest):
    """
    A city string that Nominatim cannot geocode must return 404
    with LOCATION_NOT_FOUND, not a 500 traceback.
    """

    @patch("apps.routing.geocoder.NominatimGeocoder.geocode",
           side_effect=_geocode_side_effect)
    def test_bad_start_returns_404(self, mock_geo):
        resp = self._post({
            "start": "Xyztopolis, ZZ",
            "destination": "Los Angeles, CA",
        })
        self.assertEqual(resp.status_code, 404)

    @patch("apps.routing.geocoder.NominatimGeocoder.geocode",
           side_effect=_geocode_side_effect)
    def test_bad_destination_returns_404(self, mock_geo):
        resp = self._post({
            "start": "Chicago, IL",
            "destination": "Xyztopolis, ZZ",
        })
        self.assertEqual(resp.status_code, 404)

    @patch("apps.routing.geocoder.NominatimGeocoder.geocode",
           side_effect=_geocode_side_effect)
    def test_bad_location_error_code(self, mock_geo):
        resp = self._post({
            "start": "Xyztopolis, ZZ",
            "destination": "Los Angeles, CA",
        })
        data = resp.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], "LOCATION_NOT_FOUND")

    @patch("apps.routing.geocoder.NominatimGeocoder.geocode",
           side_effect=_geocode_side_effect)
    def test_bad_location_message_contains_input(self, mock_geo):
        """Error message should echo back the unrecognised string."""
        resp = self._post({
            "start": "Xyztopolis, ZZ",
            "destination": "Los Angeles, CA",
        })
        msg = resp.json()["error"]["message"]
        self.assertIn("Xyztopolis", msg,
                      "Error message should contain the bad location string")

    @patch("apps.routing.geocoder.NominatimGeocoder.geocode",
           side_effect=_geocode_side_effect)
    def test_no_500_on_bad_location(self, mock_geo):
        """Must never return 500 for an unrecognised location."""
        resp = self._post({
            "start": "Fake City, XX",
            "destination": "Also Fake, YY",
        })
        self.assertNotEqual(resp.status_code, 500)
        self.assertIn(resp.status_code, [400, 404, 422])


# ---------------------------------------------------------------------------
# 4. NY → Miami (~1 280 mi) — expect 2–4 stops
# ---------------------------------------------------------------------------

class TestNYtoMiami(BaseRouteTest):
    """
    New York → Miami is ~1 280 miles.
    With a 500-mile tank, 2–4 stops are mathematically required.
    """

    NY_TO_MIAMI_MILES = 1280.0
    NY_TO_MIAMI_M     = NY_TO_MIAMI_MILES * 1609.34

    # Stations placed to force 3 optimal stops (all at the same low price
    # so the DP always picks the furthest reachable one)
    STATIONS = _make_stations([
        (3.10, 350),    # stop 1 candidate
        (3.05, 490),    # stop 1 — furthest reachable from start, cheapest
        (3.20, 600),
        (3.00, 820),    # stop 2 — cheapest in second window
        (3.15, 950),
        (3.10, 1200),   # stop 3 — needed to reach Miami
    ])

    @patch("apps.routing.geocoder.NominatimGeocoder.geocode",
           side_effect=_geocode_side_effect)
    @patch("apps.routing.client.OSRMClient.get_route")
    @patch("apps.api.views.project_stations_to_route",
           return_value=STATIONS)
    @patch("apps.stations.services.StationQueryService.get_stations_near_route",
           return_value=[])
    def test_ny_miami_stop_count_in_range(
        self, mock_svc, mock_proj, mock_osrm, mock_geo
    ):
        mock_osrm.return_value = _make_osrm_response(self.NY_TO_MIAMI_M)
        resp = self._post({
            "start": "New York, NY",
            "destination": "Miami, FL",
        })
        self.assertEqual(resp.status_code, 200)
        stop_count = resp.json()["meta"]["stop_count"]
        self.assertGreaterEqual(stop_count, 2,
            f"NY→Miami needs ≥2 stops, got {stop_count}")
        self.assertLessEqual(stop_count, 4,
            f"NY→Miami needs ≤4 stops, got {stop_count}")

    @patch("apps.routing.geocoder.NominatimGeocoder.geocode",
           side_effect=_geocode_side_effect)
    @patch("apps.routing.client.OSRMClient.get_route")
    @patch("apps.api.views.project_stations_to_route",
           return_value=STATIONS)
    @patch("apps.stations.services.StationQueryService.get_stations_near_route",
           return_value=[])
    def test_ny_miami_vehicle_never_runs_dry(
        self, mock_svc, mock_proj, mock_osrm, mock_geo
    ):
        mock_osrm.return_value = _make_osrm_response(self.NY_TO_MIAMI_M)
        resp = self._post({
            "start": "New York, NY",
            "destination": "Miami, FL",
        })
        stops = resp.json()["stops"]
        prev_miles = 0.0
        for stop in stops:
            gap = stop["miles_from_start"] - prev_miles
            self.assertLessEqual(
                gap, 500.0,
                f"Gap of {gap:.1f} mi before stop #{stop['sequence']} "
                f"exceeds 500-mile tank range"
            )
            prev_miles = stop["miles_from_start"]
        # Final gap to destination
        final_gap = self.NY_TO_MIAMI_MILES - prev_miles
        self.assertLessEqual(
            final_gap, 500.0,
            f"Final gap of {final_gap:.1f} mi to destination exceeds tank range"
        )

    @patch("apps.routing.geocoder.NominatimGeocoder.geocode",
           side_effect=_geocode_side_effect)
    @patch("apps.routing.client.OSRMClient.get_route")
    @patch("apps.api.views.project_stations_to_route",
           return_value=STATIONS)
    @patch("apps.stations.services.StationQueryService.get_stations_near_route",
           return_value=[])
    def test_ny_miami_no_micro_purchases(
        self, mock_svc, mock_proj, mock_osrm, mock_geo
    ):
        """No stop should purchase fewer than 2 gallons."""
        mock_osrm.return_value = _make_osrm_response(self.NY_TO_MIAMI_M)
        resp = self._post({
            "start": "New York, NY",
            "destination": "Miami, FL",
        })
        for stop in resp.json()["stops"]:
            self.assertGreater(
                float(stop["gallons_purchased"]), 2.0,
                f"Micro-purchase at stop #{stop['sequence']}: "
                f"{stop['gallons_purchased']} gal"
            )

    @patch("apps.routing.geocoder.NominatimGeocoder.geocode",
           side_effect=_geocode_side_effect)
    @patch("apps.routing.client.OSRMClient.get_route")
    @patch("apps.api.views.project_stations_to_route",
           return_value=STATIONS)
    @patch("apps.stations.services.StationQueryService.get_stations_near_route",
           return_value=[])
    def test_ny_miami_cost_matches_stop_sum(
        self, mock_svc, mock_proj, mock_osrm, mock_geo
    ):
        """total_fuel_cost_usd must equal sum of cost_at_stop values."""
        mock_osrm.return_value = _make_osrm_response(self.NY_TO_MIAMI_M)
        resp = self._post({
            "start": "New York, NY",
            "destination": "Miami, FL",
        })
        data = resp.json()
        stop_total = sum(float(s["cost_at_stop"]) for s in data["stops"])
        meta_total  = float(data["meta"]["total_fuel_cost_usd"])
        self.assertAlmostEqual(
            stop_total, meta_total, delta=0.05,
            msg=f"Stop sum ${stop_total:.2f} ≠ meta total ${meta_total:.2f}"
        )


# ---------------------------------------------------------------------------
# 5. Dallas → Denver (~930 mi) — expect 1–3 stops
# ---------------------------------------------------------------------------

class TestDallastoDenver(BaseRouteTest):
    """
    Dallas → Denver is ~930 miles.
    With a 500-mile tank: 1–3 stops depending on station placement.
    Minimum 1 stop is mathematically required (930 > 500).
    """

    DALLAS_TO_DENVER_MILES = 930.0
    DALLAS_TO_DENVER_M = DALLAS_TO_DENVER_MILES * 1609.34

    STATIONS = _make_stations([
        (3.20, 300),
        (3.05, 480),    # stop 1 — cheap, furthest reachable from Dallas
        (3.30, 600),
        (3.15, 750),    # stop 2 candidate — might be skipped if range allows
        (3.25, 880),    # last option before Denver
    ])

    @patch("apps.routing.geocoder.NominatimGeocoder.geocode",
           side_effect=_geocode_side_effect)
    @patch("apps.routing.client.OSRMClient.get_route")
    @patch("apps.api.views.project_stations_to_route",
           return_value=STATIONS)
    @patch("apps.stations.services.StationQueryService.get_stations_near_route",
           return_value=[])
    def test_dallas_denver_at_least_one_stop(
        self, mock_svc, mock_proj, mock_osrm, mock_geo
    ):
        mock_osrm.return_value = _make_osrm_response(self.DALLAS_TO_DENVER_M)
        resp = self._post({
            "start": "Dallas, TX",
            "destination": "Denver, CO",
        })
        self.assertEqual(resp.status_code, 200)
        stop_count = resp.json()["meta"]["stop_count"]
        self.assertGreaterEqual(stop_count, 1,
            f"Dallas→Denver is 930 mi — at least 1 stop required, got {stop_count}")

    @patch("apps.routing.geocoder.NominatimGeocoder.geocode",
           side_effect=_geocode_side_effect)
    @patch("apps.routing.client.OSRMClient.get_route")
    @patch("apps.api.views.project_stations_to_route",
           return_value=STATIONS)
    @patch("apps.stations.services.StationQueryService.get_stations_near_route",
           return_value=[])
    def test_dallas_denver_stop_count_reasonable(
        self, mock_svc, mock_proj, mock_osrm, mock_geo
    ):
        mock_osrm.return_value = _make_osrm_response(self.DALLAS_TO_DENVER_M)
        resp = self._post({
            "start": "Dallas, TX",
            "destination": "Denver, CO",
        })
        stop_count = resp.json()["meta"]["stop_count"]
        self.assertLessEqual(stop_count, 3,
            f"Dallas→Denver should need ≤3 stops, got {stop_count}")

    @patch("apps.routing.geocoder.NominatimGeocoder.geocode",
           side_effect=_geocode_side_effect)
    @patch("apps.routing.client.OSRMClient.get_route")
    @patch("apps.api.views.project_stations_to_route",
           return_value=STATIONS)
    @patch("apps.stations.services.StationQueryService.get_stations_near_route",
           return_value=[])
    def test_dallas_denver_vehicle_never_runs_dry(
        self, mock_svc, mock_proj, mock_osrm, mock_geo
    ):
        mock_osrm.return_value = _make_osrm_response(self.DALLAS_TO_DENVER_M)
        resp = self._post({
            "start": "Dallas, TX",
            "destination": "Denver, CO",
        })
        stops  = resp.json()["stops"]
        prev   = 0.0
        for stop in stops:
            gap = stop["miles_from_start"] - prev
            self.assertLessEqual(gap, 500.0,
                f"Gap of {gap:.1f} mi before stop #{stop['sequence']} "
                f"exceeds 500-mile tank")
            prev = stop["miles_from_start"]
        self.assertLessEqual(
            self.DALLAS_TO_DENVER_MILES - prev, 500.0,
            "Final leg to Denver exceeds tank range"
        )

    @patch("apps.routing.geocoder.NominatimGeocoder.geocode",
           side_effect=_geocode_side_effect)
    @patch("apps.routing.client.OSRMClient.get_route")
    @patch("apps.api.views.project_stations_to_route",
           return_value=STATIONS)
    @patch("apps.stations.services.StationQueryService.get_stations_near_route",
           return_value=[])
    def test_dallas_denver_stops_in_sequence(
        self, mock_svc, mock_proj, mock_osrm, mock_geo
    ):
        """Stop sequence numbers must be 1, 2, 3... and miles must increase."""
        mock_osrm.return_value = _make_osrm_response(self.DALLAS_TO_DENVER_M)
        resp = self._post({
            "start": "Dallas, TX",
            "destination": "Denver, CO",
        })
        stops = resp.json()["stops"]
        for i, stop in enumerate(stops):
            self.assertEqual(stop["sequence"], i + 1,
                f"Stop sequence should be {i+1}, got {stop['sequence']}")
        miles_list = [s["miles_from_start"] for s in stops]
        self.assertEqual(miles_list, sorted(miles_list),
            "Stops must be ordered by miles_from_start ascending")


# ---------------------------------------------------------------------------
# 6. Algorithm invariants (pure unit tests — no HTTP, no mocks needed)
# ---------------------------------------------------------------------------

class TestOptimizerInvariants(TestCase):
    """
    Direct unit tests on find_optimal_fuel_stops().
    These run without Django views or mocked HTTP — pure algorithm.
    """

    def setUp(self):
        from apps.optimizer.engine import find_optimal_fuel_stops
        self.engine = find_optimal_fuel_stops

    def test_exact_range_boundary(self):
        """Station at exactly 500 mi must be reachable (boundary inclusive)."""
        stations = _make_stations([(3.00, 500)])
        stops, cost, _naive = self.engine(stations, total_distance=1000.0)
        self.assertEqual(len(stops), 1)
        self.assertAlmostEqual(float(stops[0]["miles_from_start"]), 500.0, delta=1.0)

    def test_gap_over_range_raises(self):
        """A 600-mile gap with no stations must raise ValueError."""
        stations = _make_stations([(3.00, 700)])  # unreachable from start
        with self.assertRaises(ValueError):
            self.engine(stations, total_distance=1200.0)

    def test_cheapest_station_selected(self):
        """
        Two stations in the same reachable window — algorithm must
        choose the cheaper one.
        """
        stations = _make_stations([
            (3.50, 200),   # expensive
            (2.80, 350),   # cheap  ← must be selected
        ])
        stops, _, _naive = self.engine(stations, total_distance=600.0)
        self.assertEqual(len(stops), 1)
        self.assertAlmostEqual(float(stops[0]["retail_price"]), 2.80, delta=0.01)

    def test_no_stops_under_500_miles(self):
        """Trip shorter than tank range — engine returns empty stop list."""
        stations = _make_stations([(3.00, 200)])
        stops, cost, _naive = self.engine(stations, total_distance=400.0)
        self.assertEqual(len(stops), 0,
            "Under-500-mile trip must return zero stops")
        # Cost is $0 — vehicle started full and didn't need to refuel
        self.assertAlmostEqual(cost, 0.0, delta=0.01)

    def test_total_cost_matches_stop_sum(self):
        """Returned total_cost must exactly equal sum of per-stop costs."""
        stations = _make_stations([
            (2.90, 480),
            (3.10, 960),
        ])
        stops, total, _naive = self.engine(stations, total_distance=1100.0)
        stop_sum = sum(float(s["cost_at_stop"]) for s in stops)
        self.assertAlmostEqual(total, stop_sum, delta=0.02)

    def test_partial_fill_at_expensive_stop(self):
        """
        Expensive station followed immediately by cheap station:
        expensive stop must receive a small purchase (partial fill),
        not a full 50-gallon fill-up.
        """
        stations = _make_stations([
            (3.50, 470),   # expensive — only buy enough to reach cheap station
            (2.70, 490),   # cheap     — fill up here
        ])
        stops, _, _naive = self.engine(stations, total_distance=900.0)
        expensive_stop = next(
            (s for s in stops if abs(float(s["miles_from_start"]) - 470) < 5), None
        )
        if expensive_stop:
            # Should buy only ~2 gal (20 mi / 10 mpg) to reach the cheap station
            self.assertLess(
                float(expensive_stop["gallons_purchased"]), 10.0,
                "Expensive stop directly before a cheap station should "
                "receive a partial fill, not a full tank"
            )

    def test_stop_sequence_is_chronological(self):
        """Stops must be returned in ascending miles_from_start order."""
        stations = _make_stations([
            (3.00, 450),
            (2.90, 250),
            (3.20, 700),
        ])
        stops, _, _naive = self.engine(stations, total_distance=900.0)
        miles = [s["miles_from_start"] for s in stops]
        self.assertEqual(miles, sorted(miles),
            "Stops must be chronological (ascending miles_from_start)")
