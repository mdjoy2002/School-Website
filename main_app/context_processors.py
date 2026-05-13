# ফাইলের উপরে কোনো মডেল ইমপোর্ট করবেন না

def ticker_context(request):
    # ফাংশনের ভেতরে ইমপোর্ট করুন
    from .models import TickerNews 
    
    return {
        'database_tickers': TickerNews.objects.filter(is_active=True).order_by('-created_at')
    }