import contextvars

_current_request = contextvars.ContextVar("current_request", default=None)


def set_current_request(request):
    """Store the current request in a context variable."""
    return _current_request.set(request)


def get_current_request():
    """Retrieve request stored by RequestContextMiddleware."""
    try:
        return _current_request.get()
    except LookupError:
        return None


def reset_request(token):
    """Reset context variable to previous state."""
    _current_request.reset(token)