from django.contrib import admin

# Register your models here.

from .models import Student

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'student_id', 'current_class', 'class_roll', 'mobile_num')
    search_fields = ('full_name', 'student_id')