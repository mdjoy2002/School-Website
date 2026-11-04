from django import forms
from django.utils import timezone

from main_app.models import Staff
from myteacher.models import Teacher
from students.models import Student

from .models import SMSCampaign
from .services import normalize_phone_number


CLASS_SMS_CHOICES = [
    ('6', 'ষষ্ঠ শ্রেণি'),
    ('7', 'সপ্তম শ্রেণি'),
    ('8', 'অষ্টম শ্রেণি'),
    ('9', 'নবম শ্রেণি'),
    ('10', 'দশম শ্রেণি'),
]


class SMSComposeForm(forms.Form):
    gateway = forms.ChoiceField(
        choices=SMSCampaign.GATEWAY_CHOICES,
        label='SMS Gateway',
        initial='sms_net_bd',
    )
    audience = forms.ChoiceField(
        choices=SMSCampaign.AUDIENCE_CHOICES,
        label='কাদের কাছে SMS পাঠাবেন?',
    )
    title = forms.CharField(
        label='ক্যাম্পেইনের শিরোনাম',
        max_length=150,
        initial='SMS Campaign',
    )
    message = forms.CharField(
        label='আপনার বার্তা',
        widget=forms.Textarea(attrs={'rows': 6}),
        max_length=1600,
        help_text='বাংলা ও ইংরেজি—দুই ভাষাতেই লিখতে পারবেন। প্রত্যেক প্রাপকের জন্য তার category অনুযায়ী নাম ও শিক্ষার্থীর নাম স্বয়ংক্রিয়ভাবে বসবে।',
    )
    scheduled_at = forms.DateTimeField(
        label='পরে পাঠানোর সময় (ঐচ্ছিক)',
        required=False,
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
    )
    classes = forms.MultipleChoiceField(
        choices=CLASS_SMS_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='শ্রেণি নির্বাচন করুন',
    )
    selected_class = forms.ChoiceField(
        choices=[('', 'প্রথমে শ্রেণি নির্বাচন করুন'), *CLASS_SMS_CHOICES],
        required=False,
        label='শিক্ষার্থীর শ্রেণি',
    )
    selected_students = forms.ModelMultipleChoiceField(
        queryset=Student.objects.none(),
        required=False,
        widget=forms.MultipleHiddenInput,
        label='শিক্ষার্থী নির্বাচন করুন',
    )
    selected_teachers = forms.ModelMultipleChoiceField(
        queryset=Teacher.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'recipient-checkbox-list'}),
        label='শিক্ষক নির্বাচন করুন',
    )
    selected_office_staff = forms.ModelMultipleChoiceField(
        queryset=Staff.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'size': 10}),
        label='অফিস স্টাফ নির্বাচন করুন',
    )
    test_number = forms.CharField(
        required=False,
        max_length=32,
        label='পরীক্ষার মোবাইল নম্বর',
        help_text='প্রথমে নির্বাচিত gateway-তে নিজের নম্বরে পরীক্ষামূলক SMS পাঠিয়ে নিন।',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['selected_students'].queryset = Student.objects.order_by(
            'current_class', 'class_roll', 'full_name'
        )
        self.fields['selected_students'].label_from_instance = (
            lambda student: f'{student.full_name} — Class {student.current_class}, '
            f'guardian number {student.mobile_num}'
        )
        self.fields['selected_teachers'].queryset = Teacher.objects.order_by('teacher_name')
        self.fields['selected_teachers'].label_from_instance = (
            lambda teacher: f'{teacher.teacher_name} — {teacher.mobile}'
        )
        self.fields['selected_office_staff'].queryset = Staff.objects.order_by('order', 'name')
        self.fields['selected_office_staff'].label_from_instance = (
            lambda staff: f'{staff.name} — {staff.phone or "নম্বর নেই"}'
        )

    def clean(self):
        cleaned_data = super().clean()
        gateway = cleaned_data.get('gateway')
        audience = cleaned_data.get('audience')
        if audience == 'class_guardians' and not cleaned_data.get('classes'):
            self.add_error('classes', 'অন্তত একটি শ্রেণি নির্বাচন করুন।')
        elif audience == 'selected_guardians':
            selected_class = cleaned_data.get('selected_class')
            selected_students = cleaned_data.get('selected_students')
            if not selected_class:
                self.add_error('selected_class', 'প্রথমে একটি শ্রেণি নির্বাচন করুন।')
            if not selected_students:
                self.add_error('selected_students', 'অন্তত একজন শিক্ষার্থী নির্বাচন করুন।')
            elif selected_class and any(
                student.current_class != selected_class
                for student in selected_students
            ):
                self.add_error(
                    'selected_students',
                    'নির্বাচিত শিক্ষার্থীদের অবশ্যই বাছাই করা শ্রেণির হতে হবে।',
                )
        elif audience == 'selected_teachers' and not cleaned_data.get('selected_teachers'):
            self.add_error('selected_teachers', 'অন্তত একজন শিক্ষক নির্বাচন করুন।')
        elif audience == 'selected_office_staff' and not cleaned_data.get('selected_office_staff'):
            self.add_error('selected_office_staff', 'অন্তত একজন অফিস স্টাফ নির্বাচন করুন।')
        elif audience == 'test':
            number = cleaned_data.get('test_number', '')
            try:
                cleaned_data['test_number'] = normalize_phone_number(number)
            except ValueError as exc:
                self.add_error('test_number', str(exc))
        if gateway == 'httpsms' and cleaned_data.get('scheduled_at'):
            self.add_error(
                'scheduled_at',
                'httpSMS sends immediately and does not support scheduled messages.',
            )
        scheduled_at = cleaned_data.get('scheduled_at')
        if scheduled_at and scheduled_at <= timezone.now():
            self.add_error('scheduled_at', 'নির্ধারিত সময় ভবিষ্যতের হতে হবে।')
        return cleaned_data
