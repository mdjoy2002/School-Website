# ফাইলের উপরে কোনো মডেল ইমপোর্ট করবেন না

def ticker_context(request):
    from .models import TickerNews, Notice, ExamRoutine

    return {
        'database_tickers': TickerNews.objects.filter(is_active=True).order_by('-created_at'),
        'ticker_notices': Notice.objects.filter(is_active=True, show_on_ticker=True).order_by('-created_at'),
        'ticker_routines': ExamRoutine.objects.filter(show_on_ticker=True).order_by('-created_at'),
    }