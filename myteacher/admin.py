from django.contrib import admin
from django import forms
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

    def get_form(self, request, obj=None, **kwargs):
        # Create a ModelForm that excludes already-assigned subjects from the subject field
        class _AssignmentForm(forms.ModelForm):
            class Meta:
                model = TeacherSubjectAssignment
                fields = '__all__'

            def __init__(self, *args, **inner_kwargs):
                super().__init__(*args, **inner_kwargs)
                # All subject ids already assigned
                assigned_ids = list(TeacherSubjectAssignment.objects.values_list('subject_id', flat=True))
                # If editing an existing assignment, allow its subject to remain selectable
                if self.instance and getattr(self.instance, 'pk', None):
                    try:
                        assigned_ids.remove(self.instance.subject_id)
                    except ValueError:
                        pass
                self.fields['subject'].queryset = Subject.objects.exclude(pk__in=assigned_ids)

        return _AssignmentForm

    def get_class_level(self, obj):
        return f"Class {obj.subject.class_level}"
    get_class_level.short_description = 'Class'


# TeacherClassAssignment is intentionally not registered in admin
# because subject assignments already contain class information.

# ExamRoutine Admin
@admin.register(ExamRoutine)
class ExamRoutineAdmin(admin.ModelAdmin):
    list_display = ('class_name', 'group_name', 'subject_name', 'exam_date', 'exam_type')
    list_filter = ('class_name', 'exam_type', 'exam_date')
    search_fields = ('subject_name', 'class_name')
