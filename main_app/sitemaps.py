from django.contrib.sitemaps import Sitemap
from django.urls import reverse

class StaticViewSitemap(Sitemap):
    priority = 0.5
    changefreq = 'daily'

    def items(self):
        # আপনার urls.py-তে থাকা name গুলোর লিস্ট
        return [
            'home', 
            'all_notices', 
            'exam_routine', 
            'teachers_page', 
            'gallery', 
            'contact'
        ]

    def location(self, item):
        return reverse(item)

    # এটি যোগ করা হয়েছে যাতে 'Site matching query does not exist' এররটি আর না আসে
    def get_urls(self, site=None, **kwargs):
        return super().get_urls(site=None, **kwargs)