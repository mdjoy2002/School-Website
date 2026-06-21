# students/urls.py (অ্যাপের নিজস্ব ইউআরএল ফাইল)
from django.urls import path
from . import views

urlpatterns = [
    path('', views.student_home, name='student_home'),  # শিক্ষার্থী কর্নারের হোম পেজ
   
]