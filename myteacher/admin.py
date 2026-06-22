from django.contrib import admin
from .models import Subject, Mark, Teacher, TeacherSubjectAssignment, ExamRoutine

# Subject Admin
@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('subject_name', 'class_level', 'subject_type', 'has_practical', 'full_mark')
    list_filter = ('class_level', 'has_practical', 'subject_type')

# Mark Admin
@admin.register(Mark)
class MarkAdmin(admin.ModelAdmin):
    list_display = ('mark_id', 'student', 'subject', 'exam_type', 'total_mark')
    list_filter = ('exam_type', 'subject')
    readonly_fields = ('mark_id',) 

# Teacher Admin
@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('teacher_name', 'teacher_id', 'designation', 'is_class_teacher', 'class_teacher_of', 'mobile')
    list_filter = ('designation', 'is_class_teacher', 'class_teacher_of')
    search_fields = ('teacher_name', 'teacher_id', 'designation')

# Teacher Subject Assignment Admin
@admin.register(TeacherSubjectAssignment)
class SubjectAssignmentAdmin(admin.ModelAdmin):
    list_display = ('assisngsubid', 'teacher', 'subject', 'get_class_level', 'created_at')
    list_filter = ('teacher', 'subject__class_level', 'created_at')
    search_fields = ('teacher__teacher_name', 'subject__subject_name')
    readonly_fields = ('assisngsubid', 'created_at')
    
    def get_class_level(self, obj):
        return f"Class {obj.subject.class_level}"
    get_class_level.short_description = 'Class'

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Limit the subject dropdown to subjects flagged as 1st/2nd/4th paper.

        This ensures when assigning subjects to teachers the list shows
        subjects that are configured as primary/secondary/optional papers.
        """
        if db_field.name == 'subject':
            from .models import Subject
            kwargs['queryset'] = Subject.objects.filter(subject_type__in=['1', '2', '4']).order_by('class_level', 'subject_name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# TeacherClassAssignment is intentionally not registered in admin
# because subject assignments already contain class information.

# ExamRoutine Admin
@admin.register(ExamRoutine)
class ExamRoutineAdmin(admin.ModelAdmin):
    list_display = ('class_name', 'group_name', 'subject_name', 'exam_date', 'exam_type')
    list_filter = ('class_name', 'exam_type', 'exam_date')
    search_fields = ('subject_name', 'class_name')
