from django.contrib import admin

# Register your models here.

from .models import Student

CLASS_PROMOTION_MAP = {
    '6': '7',
    '7': '8',
    '8': '9',
    '9': '10',
}

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'student_id', 'date_of_birth', 'current_class', 'class_roll', 'religion', 'mobile_num')
    search_fields = ('full_name', 'student_id')
    actions = ['promote_selected_students']

    @admin.action(description='Promote selected students to next class')
    def promote_selected_students(self, request, queryset):
        promoted_count = 0
        skipped_count = 0

        for student in queryset:
            next_class = CLASS_PROMOTION_MAP.get(student.current_class)
            if next_class:
                student.current_class = next_class
                student.save()
                promoted_count += 1
            else:
                skipped_count += 1

        message = f'{promoted_count} student(s) promoted successfully.'
        if skipped_count:
            message += f' {skipped_count} student(s) were already in Class 10 and could not be promoted.'
        self.message_user(request, message)