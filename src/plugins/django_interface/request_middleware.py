from oralsin_core.adapters.context.request_context import reset_request, set_current_request


class RequestContextMiddleware:
    """Stores the request in a context var so handlers can access it."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = set_current_request(request)
        try:
            response = self.get_response(request)
        finally:
            reset_request(token)
        return response