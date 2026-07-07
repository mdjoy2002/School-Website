import sys
from django.conf import settings
from django.views.debug import technical_500_response


class InternalDebugMiddleware:
    """Middleware that shows the technical 500 debug page only to requests
    coming from IPs listed in `settings.INTERNAL_DEBUG_IPS`.

    This allows `DEBUG=False` in production while still permitting trusted
    internal users to see the detailed traceback for debugging purposes.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def _client_ip(self, request):
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')

    def __call__(self, request):
        try:
            return self.get_response(request)
        except Exception:
            client_ip = self._client_ip(request)
            if client_ip and client_ip in getattr(settings, 'INTERNAL_DEBUG_IPS', []):
                exc_type, exc_value, tb = sys.exc_info()
                return technical_500_response(request, exc_type, exc_value, tb)
            # Re-raise to let normal 500 handling occur (logging, custom handlers, etc.)
            raise
