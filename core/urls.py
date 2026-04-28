"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path
from main_app import views # views ইমপোর্ট করা হয়েছে
from django.conf import settings # settings ইমপোর্ট করা হয়েছে
from django.conf.urls.static import static # static ইমপোর্ট করা হয়েছে

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'), # হোম পেজের রুট
    
    # নোটিশ সেকশন
    path('notices/', views.all_notices_view, name='all_notices'), # সকল নোটিশ টেবিল পেজের রুট
    
    # পরীক্ষার রুটিন সেকশন
    path('exam-routine/', views.exam_routine_view, name='exam_routine'), 
    
    # শিক্ষার্থী কর্নার সেকশন (ডাইনামিক রুট)
    path('student-corner/<str:category_name>/', views.student_corner_detail, name='corner_detail'),

    # ভর্তি তথ্য সেকশন (ডাইনামিক রুট)
    path('admission/<str:category>/', views.admission_detail, name='admission_detail'),

    # --- নতুন সংযোজন: ফলাফল সেকশন (ডাইনামিক রুট) ---
    path('results/<str:category>/', views.result_category_view, name='result_category'),
    
    path('teachers/', views.teachers_view, name='teachers_page'), # শিক্ষকবৃন্দের পেজের রুট
    path('gallery/', views.gallery_view, name='gallery'), # গ্যালারি পেজের রুট
    path('contact/', views.contact_view, name='contact'), # যোগাযোগ পেজের রুট
]

# ডেভেলপমেন্ট মোডে মিডিয়া ফাইল (ছবি, পিডিএফ) দেখার জন্য
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)