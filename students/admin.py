from django.contrib import admin, messages
from django.contrib.admin.options import IS_POPUP_VAR
from django import forms
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import escape
from django.utils.translation import gettext, gettext_lazy as _
from urllib.parse import unquote

from .models import Student, StudentAdmitCard, StudentAdmitCardSetting, StudentPromotionHistory, StudentTicker, StudentResultPublication

User = get_user_model()

class StudentAdminForm(forms.ModelForm):
    new_password = forms.CharField(
        required=False, 
        label='Set new numeric password', 
        help_text='Digits only. Leave blank to keep current password.'
    )

    class Meta:
        model = Student
        fields = '__all__'

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    form = StudentAdminForm
    list_display = ('full_name', 'student_id', 'username', 'current_class', 'class_roll', 'religion', 'mobile_num', 'login_enabled')
    search_fields = ('full_name', 'student_id')
    list_filter = ('current_class', 'shift', 'religion', 'login_enabled')
    actions = ['promote_selected_students', 'generate_student_login_credentials']

    @admin.display(description='Username')
    def username(self, obj):
        return obj.user.username if obj.user else "N/A"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        new_password = form.cleaned_data.get('new_password')
        if new_password:
            user = obj.user or obj.ensure_login_credentials()[0]
            user.set_password(new_password)
            user.save(update_fields=['password'])
            obj.generated_password = new_password
            obj.user = user
            obj.save(update_fields=['generated_password', 'user'])

    @admin.action(description='Promote selected students to next class')
    def promote_selected_students(self, request, queryset):
        results = [s.promote_to_next_class() for s in queryset]
        promoted = sum(results)
        skipped = len(queryset) - promoted
        self.message_user(request, f'{promoted} promoted successfully. {skipped} skipped (already Class 10).')

    @admin.action(description='Generate login credentials for selected students')
    def generate_student_login_credentials(self, request, queryset):
        samples = []
        for student in queryset:
            user, pwd = student.ensure_login_credentials()
            if len(samples) < 20:
                samples.append(f"{student.student_id} → {user.username} / {pwd}")
        self.message_user(request, f'{len(queryset)} credential(s) generated.\nSample:\n' + '\n'.join(samples))

try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

@admin.register(User)
class CustomUserAdmin(DefaultUserAdmin):
    change_password_form = AdminPasswordChangeForm

    def user_change_password(self, request, id, form_url=""):
        user = self.get_object(request, unquote(id))
        if not self.has_change_permission(request, user):
            raise PermissionDenied
        if user is None:
            raise Http404(_("%(name)s object with primary key %(key)r does not exist.") % {
                "name": self.opts.verbose_name, "key": escape(id)})

        if request.method == "POST":
            form = self.change_password_form(user, request.POST)
            if form.is_valid():
                raw_password = form.cleaned_data.get('password1')
                user = form.save()
                if raw_password and hasattr(user, 'student_profile'):
                    student = user.student_profile
                    student.generated_password = raw_password
                    student.save(update_fields=['generated_password'])

                update_session_auth_hash(request, user)
                messages.success(request, gettext("Password changed successfully."))
                return HttpResponseRedirect(reverse(f"{self.admin_site.name}:{user._meta.app_label}_{user._meta.model_name}_change", args=(user.pk,)))
        else:
            form = self.change_password_form(user)

        context = {
            **self.admin_site.each_context(request),
            "title": _("Change password: %s") % escape(user.get_username()),
            "adminForm": admin.helpers.AdminForm(form, [(None, {"fields": list(form.base_fields)})], {}),
            "form_url": form_url,
            "form": form,
            "is_popup": (IS_POPUP_VAR in request.POST or IS_POPUP_VAR in request.GET),
            "original": user,
            "add": False,
            "change": True,
            "has_change_permission": True,
            "opts": self.opts,
        }
        return TemplateResponse(request, self.change_user_password_template or "admin/auth/user/change_password.html", context)

@admin.register(StudentAdmitCard)
class StudentAdmitCardAdmin(admin.ModelAdmin):
    list_display = ('student', 'class_level', 'exam_type', 'exam_year', 'exam_title', 'generated_at')
    search_fields = ('student__full_name', 'student__student_id', 'exam_type', 'exam_year')
    list_filter = ('class_level', 'exam_type', 'exam_year')


@admin.register(StudentPromotionHistory)
class StudentPromotionHistoryAdmin(admin.ModelAdmin):
    list_display = ('student', 'from_class', 'to_class', 'promoted_at')

@admin.register(StudentTicker)
class StudentTickerAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'show_to_all', 'is_active', 'created_at', 'updated_at')
    search_fields = ('title', 'message', 'target_students__full_name', 'target_students__student_id')
    list_filter = ('show_to_all', 'is_active', 'created_at')
    filter_horizontal = ('target_students',)
    fieldsets = (
        (None, {
            'fields': ('title', 'message', 'show_to_all', 'target_students', 'is_active')
        }),
    )

@admin.register(StudentAdmitCardSetting)
class StudentAdmitCardSettingAdmin(admin.ModelAdmin):
    list_display = ('class_level', 'exam_type', 'exam_year', 'is_enabled', 'display_name')


@admin.register(StudentResultPublication)
class StudentResultPublicationAdmin(admin.ModelAdmin):
    list_display = ('class_level', 'exam_type', 'exam_year', 'is_published', 'updated_at')
    list_filter = ('class_level', 'exam_type', 'exam_year', 'is_published')
    search_fields = ('exam_type',)
    ordering = ('-exam_year', 'class_level', 'exam_type')