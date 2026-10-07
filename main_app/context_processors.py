# ফাইলের উপরে কোনো মডেল ইম্পোর্ট করবেন না

from django.db.models import Sum
from django.utils import timezone

def ticker_context(request):
    from .models import TickerNews, Notice, ExamRoutine

    return {
        'database_tickers': TickerNews.objects.filter(is_active=True).order_by('-created_at'),
        'ticker_notices': Notice.objects.filter(is_active=True, show_on_ticker=True).order_by('-created_at'),
        'ticker_routines': ExamRoutine.objects.filter(show_on_ticker=True).order_by('-created_at'),
    }


def site_status_context(request):
    from .models import SchoolInfo

    school_info = SchoolInfo.objects.first()
    return {
        'site_last_updated': school_info.last_updated if school_info else None,
    }


def visitor_counts(request):
    from .models import DailyVisitor, VisitorProfile

    today = timezone.localdate()
    today_count = DailyVisitor.objects.filter(date=today).count()
    total_count = DailyVisitor.objects.count()
    unique_count = VisitorProfile.objects.count()

    return {
        'visitor_counts': {
            'today': today_count,
            'total': total_count,
            'unique': unique_count,
        }
    }
