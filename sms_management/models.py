import uuid

from django.conf import settings
from django.db import models


class SMSAccessSettings(models.Model):
    authorized_teachers = models.ManyToManyField(
        'myteacher.Teacher',
        blank=True,
        related_name='sms_access_settings',
        verbose_name='SMS Management ব্যবহারের অনুমতিপ্রাপ্ত শিক্ষক',
        help_text='শুধু এখানে নির্বাচিত শিক্ষকরা SMS Management ব্যবহার করতে পারবেন।',
    )

    class Meta:
        verbose_name = 'SMS access setting'
        verbose_name_plural = 'SMS access settings'

    def __str__(self):
        return 'SMS access settings'


class SMSCampaign(models.Model):
    GATEWAY_CHOICES = [
        ('sms_net_bd', 'SMS.NET.BD (paid SMS)'),
        ('httpsms', 'httpSMS (Android phone SIM)'),
    ]
    AUDIENCE_CHOICES = [
        ('all_guardians', 'সকল অভিভাবক'),
        ('class_guardians', 'নির্বাচিত শ্রেণির অভিভাবক'),
        ('selected_guardians', 'নির্বাচিত শিক্ষার্থীর অভিভাবক'),
        ('all_teachers', 'সকল শিক্ষক'),
        ('selected_teachers', 'নির্বাচিত শিক্ষক'),
        ('all_office_staff', 'সকল অফিস স্টাফ'),
        ('selected_office_staff', 'নির্বাচিত অফিস স্টাফ'),
        ('everyone', 'সকলকে SMS পাঠান (Everyone)'),
        ('test', 'একটি নম্বরে পরীক্ষামূলক SMS'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Awaiting confirmation'),
        ('sending', 'Sending'),
        ('submitted', 'Submitted to SMS.NET.BD'),
        ('accepted', 'Accepted by httpSMS'),
        ('sent', 'Sent (provider report)'),
        ('delivered', 'Delivered (provider confirmed)'),
        ('partial', 'Partially sent / needs review'),
        ('failed', 'Failed'),
        ('unknown', 'Outcome unknown; do not retry'),
    ]

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sms_campaigns',
    )
    gateway = models.CharField(
        max_length=16,
        choices=GATEWAY_CHOICES,
        default='sms_net_bd',
    )
    audience = models.CharField(max_length=32, choices=AUDIENCE_CHOICES)
    title = models.CharField(max_length=150, default='SMS Campaign')
    content = models.TextField()
    scheduled_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='draft')
    recipient_count = models.PositiveIntegerField(default=0)
    excluded_count = models.PositiveIntegerField(default=0)
    confirmation_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)
        permissions = [
            ('access_sms_dashboard', 'Can access the SMS dashboard'),
        ]

    def __str__(self):
        return f'SMS campaign {self.pk} ({self.get_status_display()})'


class SMSRecipient(models.Model):
    TYPE_CHOICES = [
        ('guardian', 'Guardian'),
        ('teacher', 'Teacher'),
        ('office_staff', 'Office Staff'),
        ('test', 'Test number'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending confirmation'),
        ('submitting', 'Submitting'),
        ('submitted', 'Submitted to SMS.NET.BD'),
        ('accepted', 'Accepted by httpSMS'),
        ('sent', 'Sent (provider report)'),
        ('delivered', 'Delivered (provider confirmed)'),
        ('failed', 'Failed'),
        ('expired', 'Expired'),
        ('unknown', 'Outcome unknown; do not retry'),
    ]

    campaign = models.ForeignKey(
        SMSCampaign,
        on_delete=models.CASCADE,
        related_name='recipients',
    )
    students = models.ManyToManyField(
        'students.Student',
        blank=True,
        related_name='sms_recipients',
    )
    teacher = models.ForeignKey(
        'myteacher.Teacher',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sms_recipients',
    )
    office_staff_record = models.ForeignKey(
        'main_app.Teacher',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sms_recipients',
        limit_choices_to={'teacher_type': 'STAFF'},
    )
    recipient_type = models.CharField(max_length=12, choices=TYPE_CHOICES)
    recipient_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=16)
    student_names = models.JSONField(default=list, blank=True)
    message = models.TextField()
    request_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    api_request_id = models.CharField(max_length=100, blank=True, db_index=True)
    provider_message_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    provider_status = models.CharField(max_length=100, blank=True)
    api_error_code = models.IntegerField(null=True, blank=True)
    api_response = models.JSONField(null=True, blank=True)
    sms_charge = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='pending')
    error_message = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('id',)
        constraints = [
            models.UniqueConstraint(
                fields=('campaign', 'phone_number'),
                name='sms_unique_phone_per_campaign',
            ),
        ]

    def __str__(self):
        return f'{self.recipient_name} ({self.phone_number})'


class SMSWebhookEvent(models.Model):
    PROCESSING_CHOICES = [
        ('processed', 'Processed'),
        ('unmatched', 'No matching recipient'),
    ]

    event_id = models.CharField(max_length=100, unique=True)
    event_type = models.CharField(max_length=64)
    message_id = models.CharField(max_length=100)
    sender_number = models.CharField(max_length=32, blank=True)
    recipient_number = models.CharField(max_length=32, blank=True)
    message_content = models.TextField(blank=True)
    event_status = models.CharField(max_length=16)
    raw_payload = models.JSONField()
    processing_status = models.CharField(
        max_length=16,
        choices=PROCESSING_CHOICES,
    )
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-received_at',)

    def __str__(self):
        return f'{self.event_type} ({self.event_id})'
