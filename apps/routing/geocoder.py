import logging
import httpx
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class NominatimGeocoder:
    """
    Client for the public Nominatim Geocoding API.
    Provides caching in Redis to prevent repeated hits to the public endpoint.
    """
    BASE_URL = "https://nominatim.openstreetmap.org/search"
    USER_AGENT = "FuelOptimizer/1.0 (contact: admin@fueloptimizer.local)"

    @classmethod
    def geocode(cls, city: str, state: str) -> tuple[float, float] | None:
        """
        Geocodes a US city and state to (latitude, longitude).
        Uses cache first.
        """
        city_clean = city.strip().lower()
        state_clean = state.strip().upper()
        
        # Cache key formulation: geo:{city_state_normalised}
        cache_key = f"geo:{city_clean}_{state_clean}"
        cached = cache.get(cache_key)
        if cached:
            logger.debug(f"Geocoder cache hit for: {city_clean}, {state_clean}")
            return cached

        # Perform HTTP call to Nominatim
        params = {
            "city": city_clean,
            "state": state_clean,
            "country": "United States",
            "format": "json",
            "limit": 1
        }
        headers = {
            "User-Agent": cls.USER_AGENT
        }
        
        try:
            response = httpx.get(cls.BASE_URL, params=params, headers=headers, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                if data:
                    lat = float(data[0]["lat"])
                    lon = float(data[0]["lon"])
                    result = (lat, lon)
                    
                    # Store in cache for 7 days (604800 seconds)
                    cache.set(cache_key, result, timeout=604800)
                    logger.info(f"Successfully geocoded and cached: {city}, {state} -> {result}")
                    return result
                else:
                    logger.warning(f"No geocoding results found for: {city}, {state}")
            else:
                logger.error(f"Nominatim returned status {response.status_code} for: {city}, {state}")
        except Exception as e:
            logger.error(f"Error geocoding {city}, {state}: {e}")

        return None
