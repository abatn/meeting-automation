import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from prometheus_client import Counter, Histogram, Gauge

logger = logging.getLogger(__name__)

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "route", "status_code"],
)

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "route"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30],
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests in progress",
    ["method", "route"],
)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        if path.startswith("/metrics") or path.startswith("/health"):
            return await call_next(request)

        normalized = self._normalize_path(path)
        method = request.method
        HTTP_REQUESTS_IN_PROGRESS.labels(method=method, route=normalized).inc()
        start = time.time()

        try:
            response = await call_next(request)
            duration = time.time() - start
            HTTP_REQUESTS_TOTAL.labels(
                method=method, route=normalized, status_code=str(response.status_code)
            ).inc()
            HTTP_REQUEST_DURATION.labels(method=method, route=normalized).observe(duration)
            return response
        except Exception as e:
            duration = time.time() - start
            HTTP_REQUESTS_TOTAL.labels(
                method=method, route=normalized, status_code="500"
            ).inc()
            HTTP_REQUEST_DURATION.labels(method=method, route=normalized).observe(duration)
            raise
        finally:
            HTTP_REQUESTS_IN_PROGRESS.labels(method=method, route=normalized).dec()

    @staticmethod
    def _normalize_path(path: str) -> str:
        parts = path.strip("/").split("/")
        normalized = []
        for i, part in enumerate(parts):
            if i == 0:
                normalized.append(part)
                continue
            if part in ("v1", "v2"):
                normalized.append(part)
                continue
            if len(part) > 36 and "-" in part:
                normalized.append("{id}")
            elif part.isdigit():
                normalized.append("{id}")
            elif len(part) > 20 and part.count("-") >= 3:
                normalized.append("{id}")
            else:
                normalized.append(part)
        return "/" + "/".join(normalized)
