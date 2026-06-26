"""
URL configuration for core project.

The urlpatterns list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
"""
from django.contrib import admin
from django.urls import include, path
from main_app import views # views ইমপোর্ট করা হয়েছে
from django.conf import settings # settings ইমপোর্ট করা হয়েছে
from django.conf.urls.static import static # static ইমপোর্ট করা হয়েছে
from django.http import HttpResponse # robots.txt এবং google verification এর জন্য ইমপোর্ট করা হয়েছে
from django.contrib.auth import views as auth_views  # Auth views import korlam

# সাইটম্যাপের জন্য প্রয়োজনীয় ইমপোর্ট
from django.contrib.sitemaps.views import sitemap
from main_app.sitemaps import StaticViewSitemap

# সাইটম্যাপ ডিকশনারি
sitemaps = {
    'static': StaticViewSitemap,
}

# robots.txt এর জন্য ফাংশন (Security এবং SEO এর জন্য আপডেট করা হয়েছে)
def robots_txt(request):
    content = (
        "User-agent: *\n"
        "Disallow: /knu2026/\n"  # অ্যাডমিন প্যানেল হাইড করা হয়েছে
        "Allow: /\n"           # বাকি সব পেজ ইনডেক্স করার অনুমতি দেওয়া হয়েছে
        "Sitemap: https://knuhighschool.pythonanywhere.com/sitemap.xml"
    )
    return HttpResponse(content, content_type="text/plain")

# গুগল ভেরিফিকেশন ফাইলের জন্য ফাংশন
def google_verify(request):
    return HttpResponse("google-site-verification: googlec5cbc4a5f7c18e19.html")

urlpatterns = [
    path('knu2026/', admin.site.urls),
    path('', views.home, name='home'), # হোম পেজের রুট
    
    # নোটিশ সেকশন
    path('notices/', views.all_notices_view, name='all_notices'), # সকল নোটিশ টেবিল পেজের রুট
    
    # পরীক্ষার রুটিন সেকশন
    path('exam-routine/', views.exam_routine_view, name='exam_routine'), 
    
    # শিক্ষার্থী কর্নার সেকশন (ডাইনামিক রুট)
    path('student-corner/<str:category_name>/', views.student_corner_detail, name='corner_detail'),

    # ভর্তি তথ্য সেকশন (ডাইনামিক রুট)
    path('admission/<str:category>/', views.admission_detail, name='admission_detail'),

    # --- ফলাফল সেকশন (ডাইনামিক রুট) ---
    path('results/<str:category>/', views.result_category_view, name='result_category'),
    
    path('teachers/', views.teachers_view, name='teachers_page'), # শিক্ষকবৃন্দের পেজের রুট
    path('gallery/', views.gallery_view, name='gallery'), # গ্যালারি পেজের রুট
    path('contact/', views.contact_view, name='contact'), # যোগাযোগ পেজের রুট

    # সাইটম্যাপের ইউআরএল পাথ
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),

    # robots.txt পাথ
    path('robots.txt', robots_txt),

    # গুগল সার্চ কনসোল ভেরিফিকেশন পাথ
    path('googlec5cbc4a5f7c18e19.html', google_verify),
    # teacher অ্যাপের ইউআরএল অন্তর্ভুক্ত করা হয়েছে
    path('myteacher/', include('myteacher.urls')),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('students/', include('students.urls')),
]

# ডেভেলপমেন্ট এবং প্রোডাকশনে মিডিয়া ও স্ট্যাটিক ফাইল দেখার জন্য। 
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    # প্রোডাকশনেও যাতে স্ট্যাটিক ফাইল কাজ করে তার জন্য
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)