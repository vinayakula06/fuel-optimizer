import time
import json
import hashlib
import logging
import urllib.parse
import concurrent.futures
from django.conf import settings
from django.core.cache import cache
from django.contrib.gis.geos import GEOSGeometry
from django.http import HttpResponse
from django.shortcuts import render
from django.views.generic import TemplateView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics, serializers
from rest_framework.pagination import PageNumberPagination

from apps.api.serializers import (
    RouteOptimizationRequestSerializer,
    RouteOptimizationResponseSerializer
)
from apps.routing.geocoder import NominatimGeocoder, reset_api_call_count, get_api_call_count
from apps.routing.client import OSRMClient
from apps.stations.models import FuelStation
from routes.models import RouteCache, RouteRequestLog
from apps.stations.services import StationQueryService
from apps.optimizer.spatial import project_stations_to_route
from apps.optimizer.engine import find_optimal_fuel_stops

logger = logging.getLogger(__name__)

# Bounding box for Continental United States
# lat: [24.396, 49.384], lon: [-125.001, -66.934]
USA_BOUNDING_BOX = {
    "min_lat": 24.396,
    "max_lat": 49.384,
    "min_lon": -125.001,
    "max_lon": -66.934
}

def is_in_continental_us(lat: float, lon: float) -> bool:
    return (USA_BOUNDING_BOX["min_lat"] <= lat <= USA_BOUNDING_BOX["max_lat"] and 
            USA_BOUNDING_BOX["min_lon"] <= lon <= USA_BOUNDING_BOX["max_lon"])


class RouteOptimizationView(APIView):
    """
    Computes the optimal sequence of fuel stops for a trip between two US locations.
    """
    
    def post(self, request, *args, **kwargs):
        t0 = time.perf_counter()
        reset_api_call_count()
        timings = {}
        
        # 1. Validate Input Request
        serializer = RouteOptimizationRequestSerializer(data=request.data)
        if not serializer.is_valid():
            errors = serializer.errors
            if "non_field_errors" in errors and isinstance(errors["non_field_errors"], list) and len(errors["non_field_errors"]) > 0:
                err = errors["non_field_errors"][0]
                if isinstance(err, dict) and "code" in err:
                    return Response({
                        "error": {
                            "code": err.get("code", "INVALID_INPUT"),
                            "message": err.get("message", "Origin and destination must differ."),
                            "field": err.get("field", "destination")
                        }
                    }, status=status.HTTP_400_BAD_REQUEST)
            if "code" in errors and "message" in errors and "field" in errors:
                return Response({
                    "error": {
                        "code": str(errors["code"][0]),
                        "message": str(errors["message"][0]),
                        "field": str(errors["field"][0])
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
            return Response({
                "error": {
                    "code": "INVALID_INPUT",
                    "message": "Invalid query parameters.",
                    "details": errors
                }
            }, status=status.HTTP_400_BAD_REQUEST)
            
        validated_data = serializer.validated_data
        start_label = validated_data["start"].strip()
        destination_label = validated_data["destination"].strip()
        tank_size_miles = validated_data["tank_size_miles"]
        mpg = validated_data["mpg"]
        max_detour_miles = validated_data["max_detour_miles"]
        
        # 2. Check Cache
        cache_str = f"{start_label.lower()}:{destination_label.lower()}:{tank_size_miles}:{mpg}:{max_detour_miles}"
        cache_key = hashlib.sha256(cache_str.encode()).hexdigest()
        
        # Check RouteCache model / Redis cache
        route_cache_obj = RouteCache.objects.filter(cache_key=cache_key).first()
        if route_cache_obj:
            logger.info("Route cache hit in database.")
            resp_json = route_cache_obj.response_json
            cache_hit_ms = round((time.perf_counter() - t0) * 1000, 1)
            resp_json["meta"]["computed_in_ms"] = cache_hit_ms
            resp_json["meta"]["timing_breakdown"] = {"cache_hit_ms": cache_hit_ms}
            
            try:
                RouteRequestLog.objects.create(
                    start_location=start_label,
                    finish_location=destination_label,
                    external_api_call_count=0,
                    was_route_cached=True,
                    response_time_ms=cache_hit_ms
                )
            except Exception as e:
                logger.warning(f"Failed to create request log: {e}")
                
            return Response(resp_json, status=status.HTTP_200_OK)
            
        # 3. Geocode Locations — run start + destination IN PARALLEL
        #    Uses a thread pool so both Nominatim HTTP calls fire simultaneously,
        #    cutting geocoding wall-time from ~1.4s sequential → ~0.7s parallel.
        _t = time.perf_counter()

        def _geocode(label: str):
            """Geocode helper: try full label first, then city/state split."""
            try:
                coords = NominatimGeocoder.geocode(label, "")
                if not coords and "," in label:
                    city, state = label.split(",", 1)
                    coords = NominatimGeocoder.geocode(city, state)
                return coords
            except Exception as exc:
                logger.warning(f"Geocoding failed for '{label}': {exc}")
                return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            fut_start = executor.submit(_geocode, start_label)
            fut_dst   = executor.submit(_geocode, destination_label)
            start_coords = fut_start.result()
            dst_coords   = fut_dst.result()

        if not start_coords:
            return Response({
                "error": {
                    "code": "LOCATION_NOT_FOUND",
                    "message": f"Could not geocode start location: '{start_label}'. Ensure the city and state are valid US locations.",
                    "field": "start"
                }
            }, status=status.HTTP_404_NOT_FOUND)

        if not dst_coords:
            return Response({
                "error": {
                    "code": "LOCATION_NOT_FOUND",
                    "message": f"Could not geocode destination location: '{destination_label}'. Ensure the city and state are valid US locations.",
                    "field": "destination"
                }
            }, status=status.HTTP_404_NOT_FOUND)

        timings["geocode_ms"] = round((time.perf_counter() - _t) * 1000, 1)
            
        start_lat, start_lon = start_coords
        dst_lat, dst_lon = dst_coords
        
        # Validate locations are in Continental USA
        if not is_in_continental_us(start_lat, start_lon):
            return Response({
                "error": {
                    "code": "INVALID_INPUT",
                    "message": f"Start location '{start_label}' is outside the continental United States."
                }
            }, status=status.HTTP_400_BAD_REQUEST)
            
        if not is_in_continental_us(dst_lat, dst_lon):
            return Response({
                "error": {
                    "code": "INVALID_INPUT",
                    "message": f"Destination location '{destination_label}' is outside the continental United States."
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        # 4. OSRM Routing
        _t = time.perf_counter()
        try:
            osrm_data = OSRMClient.get_route(start_lat, start_lon, dst_lat, dst_lon)
        except Exception as e:
            return Response({
                "error": {
                    "code": "ROUTING_API_DOWN",
                    "message": "OSRM routing service is temporarily unavailable.",
                    "details": str(e)
                }
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        timings["osrm_ms"] = round((time.perf_counter() - _t) * 1000, 1)

        if not osrm_data or "routes" not in osrm_data or not osrm_data["routes"]:
            return Response({
                "error": {
                    "code": "ROUTE_IMPOSSIBLE",
                    "message": "No driving route exists between these locations."
                }
            }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
            
        route_data = osrm_data["routes"][0]
        route_geojson = {
            "type": "Feature",
            "geometry": route_data["geometry"],
            "properties": {
                "distance_m": route_data["distance"],
                "duration_s": route_data["duration"]
            }
        }
        
        total_distance_meters = route_data["distance"]
        total_distance_miles = round(total_distance_meters * 0.000621371, 2)
        
        # 5. Corridor Queries using PostGIS
        _t = time.perf_counter()
        try:
            route_geom = GEOSGeometry(json.dumps(route_data["geometry"]))
            stations = StationQueryService.get_stations_near_route(route_geom, max_detour_miles)
        except Exception as e:
            logger.error(f"PostGIS corridor query failed: {e}")
            return Response({
                "error": {
                    "code": "DATABASE_ERROR",
                    "message": "Spatial query execution failed.",
                    "details": str(e)
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        timings["db_query_ms"] = round((time.perf_counter() - _t) * 1000, 1)
            
        # 6. Project stations onto the route polyline
        _t = time.perf_counter()
        polyline_coords = route_data["geometry"]["coordinates"] # List of [lon, lat]
        
        station_dicts = [
            {
                'id': station.opis_id,
                'name': station.name,
                'address': station.address,
                'city': station.city,
                'state': station.state,
                'retail_price': float(station.retail_price),
                'latitude': station.location.y,
                'longitude': station.location.x,
            }
            for station in stations
        ]
        timings["dict_build_ms"] = round((time.perf_counter() - _t) * 1000, 1)
        
        _t2 = time.perf_counter()
        projected_stations = project_stations_to_route(station_dicts, polyline_coords)
        timings["projection_ms"] = round((time.perf_counter() - _t2) * 1000, 1)
                
        # 7. Run DP Optimization
        _t = time.perf_counter()
        try:
            stops, total_cost, naive_cost = find_optimal_fuel_stops(
                projected_stations,
                total_distance_miles,
                tank_range=tank_size_miles,
                mpg=mpg
            )
        except ValueError as e:
            return Response({
                "error": {
                    "code": "ROUTE_IMPOSSIBLE",
                    "message": str(e),
                    "details": "Try increasing the detour search radius or verify fuel capacity."
                }
            }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        timings["algorithm_ms"] = round((time.perf_counter() - _t) * 1000, 1)
            
        # 8. Assemble response JSON
        stop_results = []
        for i, stop in enumerate(stops, 1):
            stop_results.append({
                "sequence": i,
                "station_name": stop["name"],
                "address": stop["address"],
                "city": stop["city"],
                "state": stop["state"],
                "retail_price": f"{stop['retail_price']:.3f}",
                "lat": stop["latitude"],
                "lon": stop["longitude"],
                "miles_from_start": round(stop["miles_from_start"], 2),
                "gallons_purchased": round(stop["gallons_to_pump"], 2),
                "cost_at_stop": f"{stop['estimated_cost']:.2f}",
                "miles_remaining_in_tank_on_arrival": stop["miles_remaining_in_tank_on_arrival"]
            })
            
        total_fuel_gallons = round(total_distance_miles / mpg, 2)
        timings["total_ms"] = round((time.perf_counter() - t0) * 1000, 1)

        # Savings vs naive (fill at average corridor price)
        savings_usd = round(naive_cost - total_cost, 2)
        savings_pct = round((savings_usd / naive_cost * 100), 1) if naive_cost > 0 else 0.0

        map_url = self._build_map_url(request, cache_key)

        response_data = {
            "meta": {
                "start": start_label,
                "destination": destination_label,
                "total_distance_miles": total_distance_miles,
                "total_fuel_gallons": total_fuel_gallons,
                "total_fuel_cost_usd": f"{total_cost:.2f}",
                "naive_cost_usd": f"{naive_cost:.2f}",
                "savings_usd": f"{savings_usd:.2f}",
                "savings_pct": savings_pct,
                "stop_count": len(stop_results),
                "assumed_tank_full_at_start": True,
                "routing_api_calls": 1,
                "algorithm": "DP optimal — O(N·K) early-exit, parallel geocoding, tank-state-aware partial-fill",
                "computed_in_ms": timings["total_ms"],
                "timing_breakdown": timings,
            },
            "stops": stop_results,
            "route": {
                "geojson": route_geojson,
                "map_url": map_url
            }
        }
        
        # Save cache to DB RouteCache
        try:
            RouteCache.objects.create(
                cache_key=cache_key,
                start_location=start_label,
                finish_location=destination_label,
                total_miles=total_distance_miles,
                total_cost=total_cost,
                stop_count=len(stop_results),
                response_json=response_data
            )
        except Exception as e:
            logger.warning(f"Failed to save route to database cache: {e}")
            
        # Log this request to RouteRequestLog
        try:
            RouteRequestLog.objects.create(
                start_location=start_label,
                finish_location=destination_label,
                external_api_call_count=get_api_call_count(),
                was_route_cached=False,
                response_time_ms=timings["total_ms"]
            )
        except Exception as e:
            logger.warning(f"Failed to create request log: {e}")
            
        return Response(response_data, status=status.HTTP_200_OK)

    def _build_map_url(self, request, cache_key):
        """Generate the map page URL with cache_key query param."""
        return request.build_absolute_uri(f"/api/v1/map/?cache_key={cache_key}")


class RoutePreviewView(APIView):
    """
    Returns route GeoJSON without running optimizer (just fetches route from OSRM).
    """
    
    def post(self, request, *args, **kwargs):
        serializer = RouteOptimizationRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        start_label = serializer.validated_data["start"].strip()
        destination_label = serializer.validated_data["destination"].strip()
        
        start_coords = NominatimGeocoder.geocode(start_label, "")
        dst_coords = NominatimGeocoder.geocode(destination_label, "")
        if not start_coords or not dst_coords:
            return Response({"error": "Failed to geocode locations"}, status=status.HTTP_404_NOT_FOUND)
            
        start_lat, start_lon = start_coords
        dst_lat, dst_lon = dst_coords
        
        osrm_data = OSRMClient.get_route(start_lat, start_lon, dst_lat, dst_lon)
        if not osrm_data or "routes" not in osrm_data:
            return Response({"error": "No route found"}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
            
        route_data = osrm_data["routes"][0]
        route_geojson = {
            "type": "Feature",
            "geometry": route_data["geometry"],
            "properties": {
                "distance_m": route_data["distance"],
                "duration_s": route_data["duration"]
            }
        }
        return Response({
            "start": start_label,
            "destination": destination_label,
            "total_distance_miles": round(route_data["distance"] * 0.000621371, 2),
            "route": route_geojson
        }, status=status.HTTP_200_OK)


class MapView(APIView):
    """
    Returns a Leaflet.js HTML page that draws the polyline and optimal fuel stops.
    """
    
    def get(self, request, *args, **kwargs):
        cache_key = request.GET.get("cache_key")
        if not cache_key:
            return HttpResponse("Missing cache_key query parameter", status=400)
            
        route_cache = RouteCache.objects.filter(cache_key=cache_key).first()
        if not route_cache:
            return HttpResponse("Route not found in cache", status=404)
            
        data = route_cache.response_json
        
        # Render a self-contained HTML page with Leaflet.js
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Fuel Optimizer Route Map</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        body, html {{ margin: 0; padding: 0; height: 100%; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
        #map {{ width: 100%; height: 100%; }}
        .info-panel {{
            position: absolute;
            top: 20px;
            right: 20px;
            z-index: 1000;
            background: rgba(255, 255, 255, 0.95);
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            max-width: 320px;
            max-height: 80%;
            overflow-y: auto;
            border: 1px solid #eee;
        }}
        .info-panel h2 {{ margin: 0 0 10px 0; font-size: 18px; color: #1e293b; }}
        .info-panel p {{ margin: 5px 0; font-size: 14px; color: #64748b; }}
        .stat {{ font-weight: bold; color: #0f172a; }}
        .stop-item {{
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px solid #e2e8f0;
            font-size: 13px;
        }}
        .stop-item-title {{ font-weight: bold; color: #1d4ed8; }}
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="info-panel">
        <h2>Trip Summary</h2>
        <p>Start: <span class="stat">{data["meta"]["start"]}</span></p>
        <p>End: <span class="stat">{data["meta"]["destination"]}</span></p>
        <p>Total Distance: <span class="stat">{data["meta"]["total_distance_miles"]} miles</span></p>
        <p>Total Cost: <span class="stat" style="color: #16a34a">${data["meta"]["total_fuel_cost_usd"]}</span></p>
        <p>Refuel Stops: <span class="stat">{data["meta"]["stop_count"]}</span></p>
        
        <h3>Stops</h3>
        {"".join([f'<div class="stop-item"><div class="stop-item-title">#{s["sequence"]} {s["station_name"]}</div><p>City: {s["city"]}, {s["state"]}<br/>Price: ${s["retail_price"]}/gal<br/>Purchase: {s["gallons_purchased"]} gal (${s["cost_at_stop"]})<br/>Range on arrival: {s["miles_remaining_in_tank_on_arrival"]} mi</p></div>' for s in data["stops"] if "station_name" in s])}
    </div>

    <script>
        var map = L.map('map').setView([39.8283, -98.5795], 4);
        
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '&copy; OpenStreetMap contributors'
        }}).addTo(map);

        // Parse route GeoJSON from python response
        var routeGeoJSON = {json.dumps(data["route"]["geojson"])};
        var routeLayer = L.geoJSON(routeGeoJSON, {{
            style: {{ color: '#3b82f6', weight: 5, opacity: 0.75 }}
        }}).addTo(map);
        
        map.fitBounds(routeLayer.getBounds(), {{ padding: [50, 50] }});

        // Add Stops to map
        var stops = {json.dumps(data["stops"])};
        stops.forEach(function(stop) {{
            var marker = L.marker([stop.lat, stop.lon]).addTo(map);
            var popupContent = `
                <div style="font-family: sans-serif;">
                    <h3 style="margin: 0 0 5px 0; color: #1d4ed8;">#${{stop.sequence}} ${{stop.station_name}}</h3>
                    <p style="margin: 3px 0; font-size: 12px; color: #4b5563;">${{stop.address}}</p>
                    <p style="margin: 3px 0; font-size: 13px; font-weight: bold;">Price: $${{stop.retail_price}}/gal</p>
                    <p style="margin: 3px 0; font-size: 12px;">Pump: ${{stop.gallons_purchased}} gal (Est. Cost: $${{stop.cost_at_stop}})</p>
                    <p style="margin: 3px 0; font-size: 11px; color: #9ca3af;">Remaining in tank: ${{stop.miles_remaining_in_tank_on_arrival}} miles</p>
                </div>
            `;
            marker.bindPopup(popupContent);
        }});
    </script>
</body>
</html>
        """
        return HttpResponse(html_content, content_type="text/html")


class HealthCheckView(APIView):
    """
    Checks database connection, Redis server health, and OSRM demo routing status.
    """
    
    def get(self, request, *args, **kwargs):
        # 1. DB Health
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            db_status = "healthy"
        except Exception as e:
            db_status = f"unhealthy: {e}"

        # 2. Redis Health
        try:
            cache.set("health_check_redis", "ok", timeout=5)
            redis_val = cache.get("health_check_redis")
            redis_status = "healthy" if redis_val == "ok" else "unhealthy"
        except Exception as e:
            redis_status = f"unhealthy: {e}"

        # 3. OSRM Routing Status
        try:
            import httpx
            # Query cheap routing ping
            url = f"{settings.OSRM_BASE_URL}/route/v1/driving/-87.629798,41.878114;-87.629798,41.878114"
            response = httpx.get(url, timeout=2.0)
            osrm_status = "healthy" if response.status_code == 200 else f"unhealthy: HTTP {response.status_code}"
        except Exception as e:
            osrm_status = f"unhealthy: {e}"

        overall_status = "healthy" if (
            db_status == "healthy" and 
            redis_status == "healthy" and 
            osrm_status == "healthy"
        ) else "unhealthy"
        
        status_code = status.HTTP_200_OK if overall_status == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE

        return Response({
            "status": overall_status,
            "services": {
                "database": db_status,
                "redis": redis_status,
                "osrm": osrm_status
            }
        }, status=status_code)


class FuelStationPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class StationListView(generics.ListAPIView):
    """
    Provides a paginated list of imported fuel stations (mainly for verification and debugging).
    """
    serializer_class = serializers.Serializer
    pagination_class = FuelStationPagination
    
    def get_queryset(self):
        return FuelStation.objects.all().order_by('opis_id', 'retail_price')

    def list(self, request, *args, **kwargs):
        # We manually serialize to avoid writing a heavy model serializer for basic admin debug
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            data = [{
                "opis_id": s.opis_id,
                "name": s.name,
                "address": s.address,
                "city": s.city,
                "state": s.state,
                "rack_id": s.rack_id,
                "retail_price": str(s.retail_price),
                "latitude": s.location.y if s.location else None,
                "longitude": s.location.x if s.location else None,
                "geocoded_at": s.geocoded_at
            } for s in page]
            return self.get_paginated_response(data)

        data = [{
            "opis_id": s.opis_id,
            "name": s.name,
            "address": s.address,
            "city": s.city,
            "state": s.state,
            "rack_id": s.rack_id,
            "retail_price": str(s.retail_price),
            "latitude": s.location.y if s.location else None,
            "longitude": s.location.x if s.location else None,
            "geocoded_at": s.geocoded_at
        } for s in queryset]
        return Response(data)
