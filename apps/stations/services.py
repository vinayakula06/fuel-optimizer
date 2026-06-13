import logging
from django.contrib.gis.measure import D
from django.conf import settings
from apps.stations.models import FuelStation

logger = logging.getLogger(__name__)


class StationQueryService:
    """
    Handles spatial queries against the FuelStation database to find candidates near route corridors.
    """
    
    @classmethod
    def get_stations_near_route(cls, route_geom, search_radius_miles: float = None) -> list[FuelStation]:
        """
        Queries all fuel stations located within search_radius_miles from the route geometry.
        Returns a list of FuelStation model instances.
        """
        if search_radius_miles is None:
            search_radius_miles = settings.FUEL_SEARCH_RADIUS_MILES
            
        logger.info(f"Querying stations within {search_radius_miles} miles of route corridor...")
        
        # Convert miles to degrees (1 degree ≈ 69.0 miles) for geographic SRID 4326
        radius_degrees = search_radius_miles / 69.0
        stations = FuelStation.objects.filter(
            location__dwithin=(route_geom, radius_degrees)
        )
        
        station_list = list(stations)
        logger.info(f"Found {len(station_list)} candidate stations near the route.")
        return station_list
