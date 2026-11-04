from django.contrib import admin

from .models import SMSAccessSettings, SMSCampaign, SMSRecipient


@admin.register(SMSAccessSettings)
class SMSAccessSettingsAdmin(admin.ModelAdmin):
    list_display = ('id', 'authorized_teacher_count')
    list_display_links = ('id',)
    fields = ('authorized_teachers',)
    filter_horizontal = ('authorized_teachers',)

    @admin.display(description='অনুমতিপ্রাপ্ত শিক্ষক')
    def authorized_teacher_count(self, obj):
        return obj.authorized_teachers.count()

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser and not SMSAccessSettings.objects.exists()

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SMSCampaign)
class SMSCampaignAdmin(admin.ModelAdmin):
    change_list_template = 'admin/sms_management/smscampaign/change_list.html'
    list_display = ('id', 'title', 'gateway', 'audience', 'status', 'recipient_count', 'created_by', 'created_at')
    list_filter = ('gateway', 'audience', 'status', 'created_at')
    search_fields = ('title', 'content', 'created_by__username')
    readonly_fields = (
        'created_by',
        'gateway',
        'audience',
        'title',
        'content',
        'scheduled_at',
        'status',
        'recipient_count',
        'excluded_count',
        'confirmation_token',
        'created_at',
        'submitted_at',
        'completed_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm('sms_management.access_sms_dashboard')


@admin.register(SMSRecipient)
class SMSRecipientAdmin(admin.ModelAdmin):
    list_display = ('recipient_name', 'recipient_type', 'phone_number', 'status', 'api_request_id', 'campaign', 'updated_at')
    list_filter = ('recipient_type', 'status', 'created_at')
    search_fields = ('recipient_name', 'phone_number', 'api_request_id', 'campaign__title', 'campaign__content')
    readonly_fields = tuple(field.name for field in SMSRecipient._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm('sms_management.access_sms_dashboard')
