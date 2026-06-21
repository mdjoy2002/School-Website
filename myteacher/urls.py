from django.urls import path
from . import views

app_name = "myteacher"

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard_view, name='dashboard'), # নতুন ড্যাশবোর্ড পাথ
    path('mark-entry/', views.mark_entry_view, name='mark_entry'),
    path('mark-entry/history/', views.mark_entry_history_view, name='mark_entry_history'),
    path('profile/', views.teacher_profile, name='profile'),

    path('manage-routine/', views.manage_routine_view, name='manage_routine'),
    path('view-routine/', views.view_routine, name='view_routine'),
    path('student-corner/', views.student_corner_view, name='student_corner'),
    path('id-cards/', views.id_cards_view, name='id_cards'),
    path('seat-plan/', views.seat_plan_view, name='seat_plan'),
    path('seat-plan/generate/', views.generate_seat_plan, name='generate_seat_plan'),
    path('student-results/', views.student_results_view, name='student_results'),
    path('student-results/pdf/<int:student_id>/', views.student_results_pdf_view, name='student_result_pdf'),
    path('delete-routine/<int:id>/', views.delete_routine, name='delete_routine'),
    path('copy-routine/<int:from_id>/<str:target_class>/', views.copy_routine, name='copy_routine'),
    path('generate-admit/', views.generate_admit_card, name='generate_admit_card'),
    path('students/', views.student_list_view, name='student_list'),
]