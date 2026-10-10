import json
import mimetypes

from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.urls import path, reverse
from django.utils.html import format_html
from .admission_pdf import admission_pdf_download_filename, ensure_admission_pdf, generate_admission_pdf
from .models import (

    Notice, TickerNews, Slider, EntryPopupImage, SchoolInfo, LeadershipProfile, CommitteeMember, AboutImage, Teacher,

    Notice, TickerNews, Slider, SchoolInfo, AboutImage, Teacher, 

    Headmaster, GeneralTeacher, Staff, GalleryCategory, GalleryImage,
    ContactMessage, ExamRoutine, StudentCornerData, AdmissionInfo, AdmissionApplication,
    AdmissionApplySettings, ResultData
)

LEADERSHIP_PROFILE_DESIGNATIONS = {
    'FOUNDER': 'প্রতিষ্ঠাতা',
    'HEADMASTER': 'প্রধান শিক্ষক',
    'PRESIDENT': 'সভাপতি',
    'COMMITTEE': 'ম্যানেজিং কমিটি',
}


class LeadershipProfileForm(forms.ModelForm):
    designation = forms.CharField(required=False, max_length=150, label='পদবি')

    class Meta:
        model = LeadershipProfile
        fields = '__all__'

    @staticmethod
    def get_default_designation(profile_type):
        return LEADERSHIP_PROFILE_DESIGNATIONS.get(profile_type, '')

    def clean_designation(self):
        designation = (self.cleaned_data.get('designation') or '').strip()
        if designation:
            return designation

        profile_type = self.cleaned_data.get('profile_type')
        if profile_type:
            return self.get_default_designation(profile_type)

        return designation

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        initial_profile_type = self.initial.get('profile_type') or getattr(self.instance, 'profile_type', '')
        if initial_profile_type and not self.initial.get('designation') and not self.instance.designation:
            self.fields['designation'].initial = self.get_default_designation(initial_profile_type)




# --- নোটিশ বোর্ড (Notice Management) সেকশন ---
@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ('title', 'show_on_ticker', 'show_on_dashboard', 'is_new', 'is_active', 'created_at')
    list_editable = ('show_on_ticker', 'show_on_dashboard', 'is_new', 'is_active')
    list_filter = ('show_on_ticker', 'show_on_dashboard', 'is_active', 'created_at')
    search_fields = ('title',)

@admin.register(TickerNews)
class TickerNewsAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'created_at')
    list_editable = ('is_active',)
    list_filter = ('is_active', 'created_at')
    search_fields = ('title',)

admin.site.register(Slider)


@admin.register(EntryPopupImage)
class EntryPopupImageAdmin(admin.ModelAdmin):
    list_display = ('thumbnail', 'image_name', 'title', 'is_active', 'order', 'created_at')
    list_editable = ('is_active', 'order')
    list_filter = ('is_active', 'created_at')
    search_fields = ('title', 'image')
    readonly_fields = ('thumbnail', 'created_at', 'updated_at')
    ordering = ('order', 'pk')

    @admin.display(description='প্রিভিউ')
    def thumbnail(self, obj):
        if not obj or not obj.image:
            return 'ছবি নেই'
        if not obj.image.storage.exists(obj.image.name):
            return 'ছবি পাওয়া যায়নি'
        from django.utils.html import format_html

        return format_html(
            '<img src="{}" alt="{}" style="max-width: 120px; max-height: 80px; object-fit: contain;">',
            obj.image.url,
            obj.title or obj.image.name,
        )

    @admin.display(description='ছবির নাম', ordering='image')
    def image_name(self, obj):
        return obj.image.name.rsplit('/', 1)[-1] if obj.image else 'ছবি নেই'


# --- পরীক্ষার রুটিন (Exam Routine) সেকশন ---
@admin.register(ExamRoutine)
class ExamRoutineAdmin(admin.ModelAdmin):
    list_display = ('title', 'target_class', 'show_on_ticker', 'show_on_notice', 'created_at')
    list_editable = ('show_on_ticker', 'show_on_notice')
    list_filter = ('target_class', 'show_on_ticker', 'show_on_notice', 'created_at')
    search_fields = ('title',)

# --- শিক্ষার্থী কর্নার (Student Corner) সেকশন ---
@admin.register(StudentCornerData)
class StudentCornerDataAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'created_at')
    list_filter = ('category', 'created_at')
    search_fields = ('title',)

# --- ভর্তি তথ্য (Admission Info) সেকশন ---
@admin.register(AdmissionInfo)
class AdmissionInfoAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'created_at')
    list_filter = ('category', 'created_at')
    search_fields = ('title',)


@admin.register(AdmissionApplication)
class AdmissionApplicationAdmin(admin.ModelAdmin):
    list_display = (
        'application_id', 'student_name', 'application_class', 'class_roll_number',
        'payment_method', 'payment_amount', 'payment_status', 'status',
        'submitted_at', 'pdf_download',
    )
    list_filter = ('status', 'payment_status', 'admission_class', 'academic_year', 'submitted_at')
    search_fields = (
        'application_id',
        'email',
        'application_data__student_name_bn',
        'application_data__student_name_en',
        'application_data__father_name_bn',
        'application_data__father_name_en',
        'application_data__father_name',
        'application_data__mother_name_bn',
        'application_data__mother_name_en',
        'application_data__mother_name',
        'application_data__guardian_name',
    )
    readonly_fields = (
        'application_id', 'email', 'admission_class', 'academic_year',
        'class_roll_number', 'assigned_roll', 'application_fee',
        'payment_method_display', 'submitted_at',
        'student_photo_preview', 'pdf_download', 'application_data_display',
    )
    fields = (
        'application_id', 'status', 'payment_status', 'payment_method_display',
        'application_fee', 'admission_class', 'academic_year', 'class_roll_number',
        'assigned_class', 'assigned_section', 'assigned_roll', 'approver_name',
        'admission_confirmed_at', 'office_comment', 'email', 'submitted_at',
        'student_photo_preview', 'pdf_download', 'application_data_display',
    )
    date_hierarchy = 'submitted_at'

    def get_urls(self):
        custom_urls = [
            path(
                '<path:object_id>/download-pdf/',
                self.admin_site.admin_view(self.download_pdf_view),
                name='main_app_admissionapplication_download_pdf',
            ),
            path(
                '<path:object_id>/student-photo/',
                self.admin_site.admin_view(self.student_photo_view),
                name='main_app_admissionapplication_student_photo',
            ),
        ]
        return custom_urls + super().get_urls()

    def download_pdf_view(self, request, object_id):
        application = self.get_object(request, object_id)
        if application is None:
            raise Http404
        if not self.has_view_or_change_permission(request, application):
            raise PermissionDenied
        ensure_admission_pdf(application)
        filename = admission_pdf_download_filename(application)
        return FileResponse(application.pdf_file.open('rb'), as_attachment=True, filename=filename)

    def student_photo_view(self, request, object_id):
        application = self.get_object(request, object_id)
        if (
            application is None
            or not application.student_photo
            or not application.student_photo.storage.exists(application.student_photo.name)
        ):
            raise Http404
        if not self.has_view_or_change_permission(request, application):
            raise PermissionDenied
        content_type = mimetypes.guess_type(application.student_photo.name)[0] or 'application/octet-stream'
        return FileResponse(application.student_photo.open('rb'), content_type=content_type)

    @admin.display(description='শিক্ষার্থীর নাম', ordering='submitted_at')
    def student_name(self, obj):
        return obj.application_data.get('student_name_bn', 'নাম নেই')

    @admin.display(description='শিক্ষাবর্ষ')
    def application_year(self, obj):
        return obj.application_data.get('academic_year', '-')

    @admin.display(description='পেমেন্ট মাধ্যম')
    def payment_method(self, obj):
        return obj.application_data.get('payment_method_display', '-')

    @admin.display(description='আবেদন ফি')
    def payment_amount(self, obj):
        return f"৳ {obj.application_data.get('application_fee', '0.00')}"

    @admin.display(description='পেমেন্ট রেফারেন্স')
    def payment_reference(self, obj):
        return obj.application_data.get('payment_reference', '-')

    @admin.display(description='ছবি')
    def student_photo_preview(self, obj):
        if not obj.student_photo:
            return 'ছবি নেই'
        url = reverse('admin:main_app_admissionapplication_student_photo', args=(obj.pk,))
        return format_html(
            '<img src="{}" alt="শিক্ষার্থীর ছবি" style="max-width: 140px; max-height: 160px;">',
            url,
        )

    @admin.display(description='PDF ফরম')
    def pdf_download(self, obj):
        url = reverse('admin:main_app_admissionapplication_download_pdf', args=(obj.pk,))
        return format_html('<a href="{}">PDF ডাউনলোড / তৈরি করুন</a>', url)

    @admin.display(description='আবেদনের পূর্ণ তথ্য')
    def application_data_display(self, obj):
        return format_html(
            '<pre style="white-space: pre-wrap; font-family: inherit;">{}</pre>',
            json.dumps(obj.application_data, ensure_ascii=False, indent=2),
        )

    def has_add_permission(self, request):
        return False

    @admin.display(description='শ্রেণি')
    def application_class(self, obj):
        return obj.get_admission_class_display() if obj.admission_class else '-'

    @admin.display(description='পেমেন্ট মাধ্যম')
    def payment_method_display(self, obj):
        return obj.application_data.get('payment_method_display', '-')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        obj.application_data.update({
            'application_id': obj.application_id,
            'admission_class': obj.get_assigned_class_display() or obj.assigned_class,
            'roll_no': str(obj.assigned_roll or obj.class_roll_number or ''),
            'admission_status': obj.get_status_display(),
            'payment_status': obj.get_payment_status_display(),
            'assigned_class': obj.get_assigned_class_display() or obj.assigned_class,
            'assigned_section': obj.get_assigned_section_display() or obj.assigned_section,
            'assigned_roll': str(obj.assigned_roll or obj.class_roll_number or ''),
            'approver_name': obj.approver_name,
            'approval_date': obj.admission_confirmed_at.isoformat() if obj.admission_confirmed_at else '',
            'office_comment': obj.office_comment,
        })
        obj.save(update_fields=['application_data'])
        generate_admission_pdf(obj)


@admin.register(AdmissionApplySettings)
class AdmissionApplySettingsAdmin(admin.ModelAdmin):
    fields = (
        'is_active',
        'fee_class_6',
        'fee_class_7',
        'fee_class_8',
        'fee_class_9',
        'fee_class_10',
        'documents_class_6',
        'documents_class_7',
        'documents_class_8',
        'documents_class_9',
        'documents_class_10',
        'bkash_enabled',
        'bkash_number',
        'nagad_enabled',
        'nagad_number',
        'in_school_enabled',
        'payment_instructions',
        'ticker_text',
    )
    def has_add_permission(self, request):
        return not AdmissionApplySettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


# --- নতুন সংযোজন: ফলাফল তথ্য (Result Data) সেকশন ---
@admin.register(ResultData)
class ResultDataAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'created_at')
    list_filter = ('category', 'created_at')
    search_fields = ('title',)

# --- অভিযোগ বা বার্তা (Contact Messages) সেকশন ---
@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'subject', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'phone', 'subject')
    readonly_fields = ('name', 'phone', 'subject', 'message', 'created_at')

# --- ফটোগ্যালারি (ফোল্ডার ও ছবি আপলোড সেকশন) ---
class GalleryImageInline(admin.TabularInline):
    model = GalleryImage
    extra = 5 

@admin.register(GalleryCategory)
class GalleryCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    inlines = [GalleryImageInline]

    def save_formset(self, request, form, formset, change):
        # এটি ফাইল ক্লোজ এররটি এড়িয়ে ফাইলগুলোকে সঠিকভাবে সেভ করতে সাহায্য করবে
        instances = formset.save(commit=False)
        for obj in instances:
            obj.save()
        formset.save_m2m()

admin.site.register(GalleryImage)

# --- আমাদের সম্পর্কে সেকশন ---
class AboutImageInline(admin.TabularInline):
    model = AboutImage
    extra = 1

FIXED_MAP_IFRAME = '<iframe src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d14707.750311225953!2d89.51854200040722!3d22.84179884250969!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x39ff9bb4c9a25847%3A0x3ff0071fc27e4cf3!2sK.C.C%20Khondakar%20Naser%20Uddin%20Secondary%20School!5e0!3m2!1sen!2sbd!4v1783453950534!5m2!1sen!2sbd" width="600" height="450" style="border:0;" allowfullscreen="" loading="lazy" referrerpolicy="strict-origin-when-cross-origin"></iframe>'

@admin.register(SchoolInfo)
class SchoolInfoAdmin(admin.ModelAdmin):
    inlines = [AboutImageInline]
    readonly_fields = ('map_url',)

    def save_model(self, request, obj, form, change):
        obj.map_url = FIXED_MAP_IFRAME
        super().save_model(request, obj, form, change)


@admin.register(LeadershipProfile)
class LeadershipProfileAdmin(admin.ModelAdmin):
    form = LeadershipProfileForm
    list_display = ('profile_type', 'name', 'designation', 'image')
    list_filter = ('profile_type',)
    search_fields = ('name', 'designation')

    class Media:
        js = ('js/leadership-profile-autofill.js',)

@admin.register(CommitteeMember)
class CommitteeMemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'designation', 'phone', 'order')
    list_editable = ('order',)
    list_filter = ('category',)
    search_fields = ('name', 'designation', 'phone')


# ১. প্রতিষ্ঠান প্রধান সেকশন
@admin.register(Headmaster)
class HeadmasterAdmin(admin.ModelAdmin):
    list_display = ('name', 'designation', 'subject')
    exclude = ('teacher_type',)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(teacher_type='HEAD')

    def save_model(self, request, obj, form, change):
        obj.teacher_type = 'HEAD'
        super().save_model(request, obj, form, change)

# ২. সহকারী শিক্ষক সেকশন
@admin.register(GeneralTeacher)
class GeneralTeacherAdmin(admin.ModelAdmin):
    list_display = ('name', 'designation', 'subject', 'order')
    list_editable = ('order',)
    exclude = ('teacher_type',)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(teacher_type='TEACHER')

    def save_model(self, request, obj, form, change):
        obj.teacher_type = 'TEACHER'
        super().save_model(request, obj, form, change)

# ৩. কর্মচারী সেকশন
@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('name', 'designation', 'order')
    list_editable = ('order',)
    exclude = ('teacher_type', 'subject')

    def get_queryset(self, request):
        return super().get_queryset(request).filter(teacher_type='STAFF')

    def save_model(self, request, obj, form, change):
        obj.teacher_type = 'STAFF'
        super().save_model(request, obj, form, change)