import time
import logging

logger = logging.getLogger(__name__)


class ResponseTimingMiddleware:
    """
    Adds X-Response-Time-Ms header to every response.
    Logs slow requests (> 500ms) as warnings.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.perf_counter()
        response = self.get_response(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)

        response["X-Response-Time-Ms"] = duration_ms

        if duration_ms > 500:
            logger.warning(
                f"Slow request: {request.method} {request.path} "
                f"took {duration_ms}ms"
            )
        else:
            logger.info(
                f"{request.method} {request.path} → {duration_ms}ms"
            )

        return response
