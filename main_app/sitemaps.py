from django.contrib.sitemaps import Sitemap
from django.urls import reverse

class StaticViewSitemap(Sitemap):
    priority = 0.5
    changefreq = 'daily'

    def items(self):
        # আপনার urls.py-তে থাকা name গুলোর সাথে মিলিয়ে এই লিস্টটি তৈরি করা হয়েছে
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