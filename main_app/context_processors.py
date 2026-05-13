from .models import TickerNews

def ticker_context(request):
    return {
        'database_tickers': TickerNews.objects.filter(is_active=True).order_by('-created_at')
    }