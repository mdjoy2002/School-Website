from django.contrib import admin
from django import forms
from .models import Subject, Mark, Teacher, TeacherSubjectAssignment, ExamRoutine, Testimonial


class RoutineSubjectSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        subject = self.subjects.get(str(value))
        if subject:
            option['attrs'].update({
                'data-class-level': subject.class_level,
                'data-group-name': subject.group_name,
                'data-code': subject.subject_code,
            })
        return option


class RoutineSubjectChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, subject):
        label = f"{subject.subject_name} ({subject.subject_code or 'No code'}) — Class {subject.class_level}"
        if subject.group_name:
            label += f" — {subject.group_name}"
        return label


class ExamRoutineAdminForm(forms.ModelForm):
    subject_option = RoutineSubjectChoiceField(
        queryset=Subject.objects.all(),
        required=False,
        label="Subject",
        help_text="Choose from the subjects defined in My Teacher → Subjects.",
        widget=RoutineSubjectSelect,
    )
    subject_code_display = forms.CharField(
        required=False,
        disabled=True,
        label="Subject Code",
    )

    class Meta:
        model = ExamRoutine
        fields = (
            'class_name',
            'group_name',
            'subject_option',
            'subject_code_display',
            'exam_type',
            'exam_year',
            'exam_date',
            'exam_time',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['subject_option'].widget.subjects = {
            str(subject.pk): subject for subject in Subject.objects.all()
        }
        current_subject = None
        if self.instance.pk:
            self.initial['subject_code_display'] = self.instance.subject_code
            class_subjects = Subject.objects.filter(
                class_level=self.instance.class_name,
                subject_name=self.instance.subject_name,
                subject_code=self.instance.subject_code,
            )
            current_subject = class_subjects.filter(
                group_name=self.instance.group_name or '',
            ).first()
            if not current_subject and self.instance.group_name:
                current_subject = class_subjects.filter(group_name='').first()
        if current_subject:
            self.initial['subject_option'] = current_subject.pk
            self.initial['subject_code_display'] = current_subject.subject_code

    def clean(self):
        cleaned_data = super().clean()
        subject = cleaned_data.get('subject_option')
        class_name = cleaned_data.get('class_name')
        group_name = cleaned_data.get('group_name') or ''

        if subject:
            if subject.class_level != class_name:
                self.add_error('subject_option', "Choose a subject for the selected class.")
            elif subject.group_name and (
                class_name not in ['9', '10'] or subject.group_name != group_name
            ):
                self.add_error('subject_option', "Choose a subject for the selected group.")
        elif not self.instance.pk:
            self.add_error('subject_option', "Choose a subject before adding the routine.")
        elif (
            class_name != self.instance.class_name
            or group_name != (self.instance.group_name or '')
        ):
            self.add_error('subject_option', "Choose a subject for the selected class and group.")

        return cleaned_data

    def save(self, commit=True):
        subject = self.cleaned_data.get('subject_option')
        if subject:
            self.instance.subject_name = subject.subject_name
            self.instance.subject_code = subject.subject_code
        return super().save(commit=commit)

    class Media:
        js = ('admin/js/routine_subject_filter.js',)


# Subject Admin
@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('subject_name', 'subject_code', 'religion', 'class_level', 'group_name', 'subject_type', 'has_practical', 'full_mark')
    list_filter = ('religion', 'class_level', 'group_name', 'has_practical', 'subject_type')
    search_fields = ('subject_name', 'subject_code')

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
    def get_form(self, request, obj=None, **kwargs):
        # store obj for use in formfield_for_foreignkey
        self._obj = obj
        return super().get_form(request, obj, **kwargs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        from .models import Subject, TeacherSubjectAssignment
        if db_field.name == 'subject':
            # exclude subjects that are already assigned to some teacher
            assigned_qs = TeacherSubjectAssignment.objects.values_list('subject', flat=True)
            qs = Subject.objects.exclude(pk__in=assigned_qs)
            # if editing an existing assignment, include its current subject
            if getattr(self, '_obj', None) is not None:
                qs = Subject.objects.filter(pk__in=list(qs.values_list('pk', flat=True)) + [self._obj.subject_id])
            kwargs['queryset'] = qs
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# TeacherClassAssignment is intentionally not registered in admin
# because subject assignments already contain class information.

# ExamRoutine Admin
@admin.register(ExamRoutine)
class ExamRoutineAdmin(admin.ModelAdmin):
    form = ExamRoutineAdminForm
    list_display = ('class_name', 'group_name', 'subject_name', 'exam_date', 'exam_type')
    list_filter = ('class_name', 'exam_type', 'exam_date')
    search_fields = ('subject_name', 'class_name')


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ('serial_number', 'name', 'student', 'class_level', 'status', 'updated_at')
    list_filter = ('class_level', 'status', 'gender')
    search_fields = ('name', 'student__full_name', 'student__student_id', 'registration')
