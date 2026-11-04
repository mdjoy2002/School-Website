from django.urls import path

from . import views


app_name = 'sms_management'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('students/', views.students_for_class, name='students_for_class'),
    path('campaign/<int:campaign_id>/confirm/', views.confirm_send, name='confirm_send'),
    path('campaign/<int:campaign_id>/review-pending/', views.review_pending_campaign, name='review_pending_campaign'),
    path('campaign/<int:campaign_id>/recipient/<int:recipient_id>/delete/', views.delete_sent_recipient, name='delete_sent_recipient'),
    path('campaign/<int:campaign_id>/recipient/<int:recipient_id>/report/', views.refresh_report, name='refresh_report'),
    path('balance/', views.check_balance, name='check_balance'),
    path('webhook/', views.webhook, name='webhook'),
]
