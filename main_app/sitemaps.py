from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.contrib.sites.models import Site

class StaticViewSitemap(Sitemap):
    priority = 0.5
    changefreq = 'daily'
    protocol = 'https'

    def items(self):
        return ['home', 'all_notices', 'exam_routine', 'teachers_page', 'gallery', 'contact']

    def location(self, item):
        return reverse(item)

    # এই অংশটি সাইটম্যাপে example.com এর বদলে আপনার ডোমেইন বসিয়ে দিবে
    def get_urls(self, site=None, **kwargs):
        # ডাটাবেজ চেক না করে সরাসরি আপনার সাইট অবজেক্ট তৈরি করে দেওয়া
        site = Site(domain='knuhighschool.pythonanywhere.com', name='Khandaker Naser Uddin High School')
        return super().get_urls(site=site, **kwargs)