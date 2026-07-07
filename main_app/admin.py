from django.contrib import admin
from .models import (
    Notice, TickerNews, Slider, SchoolInfo, AboutImage, Teacher, 
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

@admin.register(TickerNews)
class TickerNewsAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'created_at')
    list_editable = ('is_active',)
    list_filter = ('is_active', 'created_at')
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