import logging
import httpx
from django.core.cache import cache
from django.conf import settings
from apps.routing.geocoder import increment_api_call_count

logger = logging.getLogger(__name__)


class OSRMClient:
    """
    Client for OSRM Route Service.
    Queries OSRM to get routes and geometries.
    """
    
    @classmethod
    def get_route(cls, src_lat: float, src_lon: float, dst_lat: float, dst_lon: float) -> dict | None:
        """
        Fetches the driving route between source and destination coordinates.
        Returns the parsed JSON response. Uses Redis cache.
        """
        # Formulate cache key: osrm:{src_lat_3dp}_{src_lon_3dp}:{dst_lat_3dp}_{dst_lon_3dp}
        # Using 3 decimal places (approx. 110 meters precision) to allow caching of nearby requests
        src_lat_3dp = round(src_lat, 3)
        src_lon_3dp = round(src_lon, 3)
        dst_lat_3dp = round(dst_lat, 3)
        dst_lon_3dp = round(dst_lon, 3)
        
        cache_key = f"osrm:{src_lat_3dp}_{src_lon_3dp}:{dst_lat_3dp}_{dst_lon_3dp}"
        cached = cache.get(cache_key)
        if cached:
            logger.info("OSRM cache hit")
            return cached

        url = f"{settings.OSRM_BASE_URL}/route/v1/driving/{src_lon},{src_lat};{dst_lon},{dst_lat}"
        params = {
            "overview": "full",
            "geometries": "geojson"
        }
        
        # Retry logic: retry once with 500 ms back-off
        retries = 2
        increment_api_call_count()
        for attempt in range(retries):
            try:
                response = httpx.get(
                    url, 
                    params=params, 
                    timeout=settings.OSRM_TIMEOUT_SECONDS
                )
                if response.status_code == 200:
                    data = response.json()
                    # Cache OSRM raw response for 6 hours (21600 seconds)
                    cache.set(cache_key, data, timeout=21600)
                    return data
                elif response.status_code >= 500 and attempt < retries - 1:
                    logger.warning(f"OSRM server error {response.status_code}, retrying in 500ms...")
                    import time
                    time.sleep(0.5)
                else:
                    logger.error(f"OSRM returned status {response.status_code}: {response.text}")
                    break
            except httpx.RequestError as e:
                if attempt < retries - 1:
                    logger.warning(f"OSRM request failed: {e}, retrying in 500ms...")
                    import time
                    time.sleep(0.5)
                else:
                    logger.error(f"OSRM request failed after retries: {e}")
                    raise

        return None
