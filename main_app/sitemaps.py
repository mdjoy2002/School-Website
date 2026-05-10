from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.contrib.sites.models import Site

class StaticViewSitemap(Sitemap):
    priority = 0.5
    changefreq = 'daily'
    protocol = 'https'  # লিঙ্কগুলোকে https হিসেবে জেনারেট করবে

    def items(self):
        # আপনার urls.py-তে যে নামগুলো (name='') দেওয়া আছে সেগুলো এখানে লিস্ট করা হয়েছে
        return [
            'home', 
            'all_notices', 
            'exam_routine', 
            'teachers_page', 
            'gallery', 
            'contact'
        ]

    def location(self, item):
        # এটি প্রতিটি নামের জন্য সঠিক URL পাথ তৈরি করবে
        return reverse(item)

    def get_urls(self, site=None, **kwargs):
        # ডাটাবেজের সেটিংসের ওপর নির্ভর না করে সরাসরি আপনার ডোমেইনটি বসিয়ে দেওয়ার জন্য এই অংশটি
        site = Site(
            domain='knuhighschool.pythonanywhere.com', 
            name='Khandaker Naser Uddin High School'
        )
        return super().get_urls(site=site, **kwargs)