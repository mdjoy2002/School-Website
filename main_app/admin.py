from django.contrib import admin
from .models import (
    Notice, Slider, SchoolInfo, AboutImage, Teacher, 
    Headmaster, GeneralTeacher, Staff, GalleryCategory, GalleryImage,
    ContactMessage, ExamRoutine, StudentCornerData, AdmissionInfo, ResultData
)

# --- নোটিশ বোর্ড (Notice Management) সেকশন ---
@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ('title', 'show_on_ticker', 'show_on_dashboard', 'is_active', 'created_at')
    list_editable = ('show_on_ticker', 'show_on_dashboard', 'is_active')
    list_filter = ('show_on_ticker', 'show_on_dashboard', 'is_active', 'created_at')
    search_fields = ('title',)

admin.site.register(Slider)

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

admin.site.register(GalleryImage)

# --- আমাদের সম্পর্কে সেকশন ---
class AboutImageInline(admin.TabularInline):
    model = AboutImage
    extra = 1

@admin.register(SchoolInfo)
class SchoolInfoAdmin(admin.ModelAdmin):
    inlines = [AboutImageInline]

# ১. প্রতিষ্ঠান প্রধান সেকশন
@admin.register(Headmaster)
class HeadmasterAdmin(admin.ModelAdmin):
    list_display = ('name', 'designation')
    exclude = ('teacher_type',)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(teacher_type='HEAD')

    def save_model(self, request, obj, form, change):
        obj.teacher_type = 'HEAD'
        super().save_model(request, obj, form, change)

# ২. সহকারী শিক্ষক সেকশন
@admin.register(GeneralTeacher)
class GeneralTeacherAdmin(admin.ModelAdmin):
    list_display = ('name', 'designation', 'order')
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
    exclude = ('teacher_type',)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(teacher_type='STAFF')

    def save_model(self, request, obj, form, change):
        obj.teacher_type = 'STAFF'
        super().save_model(request, obj, form, change)