from django.urls import path

from . import views

urlpatterns = [
    path('', views.student_home, name='student_home'),
    path('login/', views.student_login, name='student_login'),
    path('logout/', views.student_logout, name='student_logout'),
    path('dashboard/', views.student_dashboard, name='student_dashboard'),
    path('profile/<str:student_id>/', views.student_profile, name='student_profile'),
    path('credentials/', views.student_credentials_view, name='student_credentials'),
]