import uuid

from django.conf import settings
from django.utils import timezone

from .models import DailyVisitor, VisitorProfile


class VisitorTrackingMiddleware:
    COOKIE_NAME = 'visitor_uuid'
    COOKIE_MAX_AGE = 10 * 365 * 24 * 60 * 60  # 10 years
    COOKIE_SAMESITE = 'Lax'
    COOKIE_HTTPONLY = True

    def __init__(self, get_response):
        self.get_response = get_response

    def get_client_ip(self, request):
        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '') or ''

    def __call__(self, request):
        response = self.process_request(request)
        if response is not None:
            return response

        response = self.get_response(request)

        visitor_uuid = getattr(request, '_visitor_uuid', None)
        if visitor_uuid and not request.COOKIES.get(self.COOKIE_NAME):
            response.set_cookie(
                self.COOKIE_NAME,
                visitor_uuid,
                max_age=self.COOKIE_MAX_AGE,
                samesite=self.COOKIE_SAMESITE,
                httponly=self.COOKIE_HTTPONLY,
            )
        return response

    def process_request(self, request):
        if request.method != 'GET':
            return None

        if request.path.startswith(settings.STATIC_URL) or request.path.startswith(settings.MEDIA_URL):
            return None
        if request.path.startswith('/admin/'):
            return None

        session_key = request.session.session_key
        if not session_key:
            request.session.save()
            session_key = request.session.session_key

        ip_address = self.get_client_ip(request)
        visitor_uuid = request.COOKIES.get(self.COOKIE_NAME)
        if not visitor_uuid:
            visitor_uuid = str(uuid.uuid4())
            request._visitor_uuid = visitor_uuid

        profile, created = VisitorProfile.objects.get_or_create(
            visitor_uuid=visitor_uuid,
            defaults={'ip_address': ip_address},
        )

        if not created and profile.ip_address != ip_address:
            profile.ip_address = ip_address
        profile.last_visit = timezone.now()
        profile.save(update_fields=['ip_address', 'last_visit'])

        today = timezone.localdate()
        if not DailyVisitor.objects.filter(date=today, ip_address=ip_address, session_key=session_key).exists():
            DailyVisitor.objects.create(
                date=today,
                ip_address=ip_address,
                session_key=session_key,
                visitor_profile=profile,
            )

        request.visitor_profile = profile
        return None
