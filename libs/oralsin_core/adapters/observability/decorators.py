import time
from functools import wraps

from .metrics import CACHE_HITS, CACHE_MISSES, HTTP_REQUEST_COUNT, HTTP_REQUEST_LATENCY


def track_http(view_name):
    def decorator(fn):
        @wraps(fn)
        def wrapper(self, request, *args, **kwargs):
            start = time.time()
            resp = fn(self, request, *args, **kwargs)
            elapsed = time.time() - start
            status = getattr(resp, 'status_code', 200)
            HTTP_REQUEST_LATENCY.labels(
                method=request.method,
                view=view_name,
                status=str(status)
            ).observe(elapsed)
            HTTP_REQUEST_COUNT.labels(
                method=request.method,
                view=view_name,
                status=str(status)
            ).inc()
            return resp
        return wrapper
    return decorator

def cacheable(prefix_fn):
    """
    prefix_fn(*args, **kwargs) -> str, define a chave do cache.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = prefix_fn(*args, **kwargs)
            from django.core.cache import cache
            data = cache.get(key)
            if data is not None:
                CACHE_HITS.labels(service=fn.__name__).inc()
                return data
            CACHE_MISSES.labels(service=fn.__name__).inc()
            result = fn(*args, **kwargs)
            cache.set(key, result, timeout=300)
            return result
        return wrapper
    return decorator
