from functools import wraps


def track_http(view_name):
    def decorator(fn):
        @wraps(fn)
        def wrapper(self, request, *args, **kwargs):
            resp = fn(self, request, *args, **kwargs)
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
                return data
            result = fn(*args, **kwargs)
            cache.set(key, result, timeout=300)
            return result
        return wrapper
    return decorator
