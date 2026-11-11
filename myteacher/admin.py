from django.contrib import admin
from django import forms
from django.db import transaction
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
class SubjectAdminForm(forms.ModelForm):
    GROUP_ALL = 'ALL'

    middle_routine_subject = forms.CharField(
        required=False,
        label='Subject + Practical (Routine only)',
        help_text='For classes 6–8 only. This entry appears in routines, not mark entry.',
    )
    senior_routine_subject = forms.CharField(
        required=False,
        label='Practical Subject (Routine only)',
        help_text='For classes 9–10 only. This entry appears in routines, not mark entry.',
    )

    class Meta:
        model = Subject
        fields = (
            'subject_name',
            'subject_code',
            'subject_type',
            'religion',
            'class_level',
            'group_name',
            'has_practical',
            'full_mark',
        )

    class Media:
        js = ('admin/js/subject_admin_form.js',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields.pop('middle_routine_subject')
            self.fields.pop('senior_routine_subject')
        else:
            self.fields['group_name'].choices = [
                *Subject._meta.get_field('group_name').choices,
                (self.GROUP_ALL, 'All (Science, Commerce, Arts)'),
            ]

    def clean_group_name(self):
        group_name = self.cleaned_data['group_name']
        if group_name == self.GROUP_ALL:
            if self.cleaned_data.get('class_level') not in ('9', '10'):
                raise forms.ValidationError('All groups are only available for classes 9 and 10.')
            self.create_all_groups = True
            return ''
        class_level = self.cleaned_data.get('class_level')
        if group_name and class_level not in ('9', '10'):
            raise forms.ValidationError('Groups are only available for classes 9 and 10.')
        return group_name

    def clean(self):
        cleaned_data = super().clean()
        class_level = cleaned_data.get('class_level')
        middle_name = cleaned_data.get('middle_routine_subject', '').strip()
        senior_name = cleaned_data.get('senior_routine_subject', '').strip()

        if middle_name and senior_name:
            self.add_error('senior_routine_subject', 'Enter a routine-only subject in the field for this class.')
        if middle_name and class_level not in ('6', '7', '8'):
            self.add_error('middle_routine_subject', 'Use this field for classes 6–8 only.')
        if senior_name and class_level not in ('9', '10'):
            self.add_error('senior_routine_subject', 'Use this field for classes 9–10 only.')
        return cleaned_data


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    form = SubjectAdminForm
    list_display = ('subject_name', 'subject_code', 'religion', 'class_level', 'group_name', 'subject_type', 'has_practical', 'is_routine_only', 'full_mark')
    list_filter = ('religion', 'class_level', 'group_name', 'has_practical', 'is_routine_only', 'subject_type')
    search_fields = ('subject_name', 'subject_code')

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            groups = ['Science', 'Commerce', 'Arts'] if getattr(form, 'create_all_groups', False) else [form.cleaned_data.get('group_name') or '']
            obj.group_name = groups[0]
            super().save_model(request, obj, form, change)

            for group_name in groups[1:]:
                Subject.objects.create(
                    subject_name=obj.subject_name,
                    subject_code=obj.subject_code,
                    subject_type=obj.subject_type,
                    religion=obj.religion,
                    class_level=obj.class_level,
                    group_name=group_name,
                    has_practical=obj.has_practical,
                    full_mark=obj.full_mark,
                )

            routine_name = (
                form.cleaned_data.get('middle_routine_subject')
                or form.cleaned_data.get('senior_routine_subject')
                or ''
            ).strip()
            for group_name in groups:
                if routine_name:
                    Subject.objects.create(
                        subject_name=routine_name,
                        subject_type='0',
                        religion='None',
                        class_level=obj.class_level,
                        group_name=group_name,
                        is_routine_only=True,
                    )


# Mark Admin
@admin.register(Mark)
class MarkAdmin(admin.ModelAdmin):
    list_display = ('mark_id', 'student', 'subject', 'exam_type', 'total_mark')
    list_filter = ('exam_type', 'subject')
    readonly_fields = ('mark_id',) 

    def get_queryset(self, request):
        return super().get_queryset(request).filter(subject__is_routine_only=False)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'subject':
            kwargs['queryset'] = Subject.objects.filter(is_routine_only=False)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

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
            assigned_qs = TeacherSubjectAssignment.objects.filter(
                subject__is_routine_only=False,
            ).values_list('subject', flat=True)
            qs = Subject.objects.filter(is_routine_only=False).exclude(pk__in=assigned_qs)
            # if editing an existing assignment, include its current subject
            if getattr(self, '_obj', None) is not None:
                qs = Subject.objects.filter(
                    pk__in=list(qs.values_list('pk', flat=True)) + [self._obj.subject_id],
                    is_routine_only=False,
                )
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
