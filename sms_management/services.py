import base64
import binascii
import hashlib
import hmac
import json
import logging
import re
import time
import uuid

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import SMSCampaign, SMSRecipient, SMSWebhookEvent


logger = logging.getLogger(__name__)
HTTPSMS_SEND_URL = 'https://api.httpsms.com/v1/messages/send'
SCHOOL_SMS_PREFIX = 'খন্দকার নাসের উদ্দিন মাধ্যমিক বিদ্যালয়'
GUARDIAN_SCHOOL_NAME = 'খন্দকার নাসের উদ্দীন মাধ্যমিক বিদ্যালয়'
TEACHER_SCHOOL_NAME = 'খন্দকার নাসের উদ্দীন মাধ্যমিক বিদ্যালয়'
OFFICE_SCHOOL_NAME = 'খন্দকার নাসের উদ্দীন মাধ্যমিক বিদ্যালয়, খুলনা'
SMS_SIGNATURE = 'ধন্যবাদান্তে,\nপ্রধান শিক্ষক\nমোঃ সেলিম সরদার\n০১৭১৪৯৩৯১২২'
BD_LOCAL_MOBILE_PATTERN = re.compile(r'^01[3-9]\d{8}$')
BD_INTERNATIONAL_MOBILE_PATTERN = re.compile(r'^\+8801[3-9]\d{8}$')
WEBHOOK_STATUS_MAP = {
    'message.phone.sent': 'sent',
    'message.phone.delivered': 'delivered',
    'message.send.failed': 'failed',
    'message.send.expired': 'expired',
}
class SMSConfigurationError(Exception):
    pass


def normalize_phone_number(value):
    phone = re.sub(r'[\s().-]', '', str(value or '')).translate(
        str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789')
    )
    if phone.startswith('00'):
        phone = f'+{phone[2:]}'
    elif BD_LOCAL_MOBILE_PATTERN.fullmatch(phone):
        phone = f'+880{phone[1:]}'
    elif phone.startswith('880') and phone.isdigit():
        phone = f'+{phone}'

    if not BD_INTERNATIONAL_MOBILE_PATTERN.fullmatch(phone):
        raise ValueError('Enter a valid Bangladesh mobile number, e.g. 017XXXXXXXX or +88017XXXXXXXX.')
    return phone


def _render_message(template, name, student_names=()):
    personalized_message = (
        template
        .replace('{name}', name or '')
        .replace('{student_name}', ', '.join(student_names))
    )
    return f'{SCHOOL_SMS_PREFIX}\n{personalized_message}'


def render_personalized_message(recipient_type, custom_message, recipient_name='', student_names=()):
    if recipient_type == 'guardian':
        names = ', '.join(student_names) or 'আপনার সন্তান'
        return (
            f'{GUARDIAN_SCHOOL_NAME}\n\n'
            f'প্রিয় অভিভাবক, {names}-এর জন্য বিশেষ বিজ্ঞপ্তি: {custom_message}\n\n'
            f'{SMS_SIGNATURE}'
        )
    if recipient_type == 'teacher':
        return (
            f'{TEACHER_SCHOOL_NAME}\n\n'
            f'শ্রদ্ধেয় {recipient_name}, {custom_message}\n\n'
            f'{SMS_SIGNATURE}'
        )
    if recipient_type == 'office_staff':
        return (
            f'{OFFICE_SCHOOL_NAME}\n\n'
            f'প্রিয় {recipient_name},\n\n'
            f'{custom_message}\n\n'
            f'{SMS_SIGNATURE}'
        )
    if recipient_type == 'test':
        return _render_message(custom_message, recipient_name, student_names)
    raise ValueError(f'Unsupported SMS recipient type: {recipient_type}')


def resolve_recipients(
    audience,
    classes=(),
    students=(),
    teachers=(),
    office_staff=(),
    test_number='',
):
    recipients = {}
    excluded_count = 0
    duplicate_count = 0

    def add_recipient(kind, name, number, student=None, teacher=None, office_staff=None):
        nonlocal excluded_count, duplicate_count
        if not number:
            excluded_count += 1
            return
        try:
            normalized = normalize_phone_number(number)
        except ValueError:
            excluded_count += 1
            return

        existing = recipients.get(normalized)
        if existing:
            duplicate_count += 1
            if (
                kind == 'guardian'
                and existing['recipient_type'] == 'guardian'
                and student
                and student.pk not in existing['student_ids']
            ):
                existing['student_ids'].append(student.pk)
                existing['student_names'].append(student.full_name)
            return

        recipients[normalized] = {
            'recipient_type': kind,
            'recipient_name': name or 'SMS recipient',
            'phone_number': normalized,
            'student_names': [student.full_name] if student else [],
            'student_ids': [student.pk] if student else [],
            'teacher_id': teacher.pk if teacher else None,
            'office_staff_id': office_staff.pk if office_staff else None,
        }

    guardian_audiences = {'all_guardians', 'class_guardians', 'selected_guardians', 'everyone'}
    teacher_audiences = {'all_teachers', 'selected_teachers', 'everyone'}
    office_staff_audiences = {'all_office_staff', 'selected_office_staff', 'everyone'}

    if audience in guardian_audiences:
        from students.models import Student

        if audience == 'all_guardians' or audience == 'everyone':
            queryset = Student.objects.all()
        elif audience == 'class_guardians':
            queryset = Student.objects.filter(current_class__in=classes)
        else:
            queryset = students
        for student in queryset:
            add_recipient(
                'guardian',
                student.father_name or student.mother_name or student.full_name,
                student.mobile_num,
                student=student,
            )

    if audience in teacher_audiences:
        queryset = teachers
        if audience == 'all_teachers':
            from myteacher.models import Teacher

            queryset = Teacher.objects.all()
        elif audience == 'everyone':
            from myteacher.models import Teacher

            queryset = Teacher.objects.all()
        for teacher in queryset:
            add_recipient('teacher', teacher.teacher_name, teacher.mobile, teacher=teacher)

    if audience in office_staff_audiences:
        from main_app.models import Teacher as SchoolStaff

        queryset = office_staff
        if audience in ('all_office_staff', 'everyone'):
            queryset = SchoolStaff.objects.filter(teacher_type='STAFF').order_by('pk')
        for office_staff_member in queryset:
            add_recipient(
                'office_staff',
                office_staff_member.name,
                office_staff_member.phone,
                office_staff=office_staff_member,
            )

    if audience == 'test':
        add_recipient('test', 'Test recipient', test_number)
    elif audience not in (
        guardian_audiences
        | teacher_audiences
        | office_staff_audiences
    ):
        raise ValueError('Unsupported SMS audience.')

    return list(recipients.values()), excluded_count, duplicate_count


def send_sms(recipient):
    api_key = getattr(settings, 'HTTPSMS_API_KEY', '')
    try:
        sender_number = normalize_phone_number(
            getattr(settings, 'HTTPSMS_FROM_NUMBER', '')
        )
    except ValueError as exc:
        raise SMSConfigurationError('HTTPSMS_FROM_NUMBER must be configured in E.164 format.') from exc

    if not api_key:
        raise SMSConfigurationError('HTTPSMS_API_KEY is not configured.')

    payload = {
        'from': sender_number,
        'to': recipient.phone_number,
        'content': recipient.message,
        'request_id': str(recipient.request_id),
    }

    try:
        response = requests.post(
            HTTPSMS_SEND_URL,
            headers={
                'x-api-key': api_key,
                'Accept': 'application/json',
            },
            json=payload,
            timeout=(5, 20),
        )
    except requests.RequestException:
        recipient.status = 'unknown'
        recipient.error_message = 'No reliable response from httpSMS; delivery outcome is unknown. Do not retry automatically.'
        recipient.save(update_fields=('status', 'error_message', 'updated_at'))
        logger.warning(
            'httpSMS request outcome unknown for campaign=%s recipient=%s',
            recipient.campaign_id,
            recipient.pk,
        )
        return

    if response.status_code >= 500:
        recipient.status = 'unknown'
        recipient.error_message = f'httpSMS returned HTTP {response.status_code}; delivery outcome is unknown. Do not retry automatically.'
        recipient.save(update_fields=('status', 'error_message', 'updated_at'))
        logger.error(
            'httpSMS server error for campaign=%s recipient=%s status=%s',
            recipient.campaign_id,
            recipient.pk,
            response.status_code,
        )
        return

    if not response.ok:
        recipient.status = 'failed'
        recipient.error_message = f'httpSMS rejected the request (HTTP {response.status_code}).'
        recipient.save(update_fields=('status', 'error_message', 'updated_at'))
        logger.warning(
            'httpSMS rejected campaign=%s recipient=%s status=%s',
            recipient.campaign_id,
            recipient.pk,
            response.status_code,
        )
        return

    try:
        response_data = response.json()
        data = response_data['data']
        provider_message_id = data['id']
    except (ValueError, KeyError, TypeError):
        recipient.status = 'unknown'
        recipient.error_message = 'httpSMS returned an incomplete response; delivery outcome is unknown. Do not retry automatically.'
        recipient.save(update_fields=('status', 'error_message', 'updated_at'))
        logger.exception(
            'Invalid httpSMS response for campaign=%s recipient=%s',
            recipient.campaign_id,
            recipient.pk,
        )
        return

    recipient.provider_message_id = str(provider_message_id)
    recipient.provider_status = str(response_data.get('status', 'accepted'))[:100]
    update_fields = ['provider_message_id', 'provider_status', 'updated_at']
    if recipient.status == 'pending':
        recipient.status = 'accepted'
        recipient.error_message = ''
        update_fields.extend(('status', 'error_message'))
    recipient.save(update_fields=update_fields)
    logger.info(
        'httpSMS accepted campaign=%s recipient=%s provider_status=%s',
        recipient.campaign_id,
        recipient.pk,
        recipient.provider_status,
    )


def verify_webhook_token(authorization, signing_key):
    if not authorization or not signing_key:
        return False
    token = authorization.strip()
    if token.lower().startswith('bearer '):
        token = token[7:].strip()

    parts = token.split('.')
    if len(parts) != 3:
        return False

    try:
        header = json.loads(_base64url_decode(parts[0]))
        payload = json.loads(_base64url_decode(parts[1]))
        signature = _base64url_decode(parts[2])
    except (ValueError, TypeError, json.JSONDecodeError, binascii.Error):
        return False

    if not isinstance(header, dict) or not isinstance(payload, dict):
        return False
    if header.get('alg') != 'HS256':
        return False
    expected_signature = hmac.new(
        signing_key.encode('utf-8'),
        f'{parts[0]}.{parts[1]}'.encode('ascii'),
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(signature, expected_signature):
        return False

    now = time.time()
    if 'exp' in payload:
        if not isinstance(payload['exp'], (int, float)) or now >= payload['exp']:
            return False
    if 'nbf' in payload:
        if not isinstance(payload['nbf'], (int, float)) or now < payload['nbf']:
            return False
    return True


def _base64url_decode(value):
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


def process_webhook_event(event):
    if not isinstance(event, dict):
        raise ValueError('Webhook payload must be an object.')

    event_type = event.get('type')
    target_status = WEBHOOK_STATUS_MAP.get(event_type)
    if not target_status:
        return 'ignored'

    data = event.get('data')
    if not isinstance(data, dict):
        raise ValueError('Webhook event data must be an object.')

    message_id = data.get('id') or data.get('message_id')
    contact = data.get('contact')
    owner = data.get('owner')
    event_id = event.get('id')
    if not all(isinstance(value, str) and value.strip() for value in (event_id, message_id, contact, owner)):
        raise ValueError('Webhook event is missing its event ID, message ID, contact, or owner.')

    try:
        contact = normalize_phone_number(contact)
        owner = normalize_phone_number(owner)
    except ValueError as exc:
        raise ValueError('Webhook event contains an invalid phone number.') from exc

    with transaction.atomic():
        webhook_event, created = SMSWebhookEvent.objects.get_or_create(
            event_id=event_id,
            defaults={
                'event_type': event_type,
                'message_id': message_id,
                'sender_number': owner,
                'recipient_number': contact,
                'message_content': str(data.get('content') or ''),
                'event_status': target_status,
                'raw_payload': event,
                'processing_status': 'unmatched',
            },
        )
        if not created and webhook_event.processing_status != 'unmatched':
            return 'duplicate'

        recipient = SMSRecipient.objects.select_for_update().filter(
            provider_message_id=message_id,
        ).first()
        request_id = data.get('request_id')
        if recipient is None and isinstance(request_id, str) and request_id.strip():
            try:
                request_uuid = uuid.UUID(request_id)
            except ValueError:
                request_uuid = None
            if request_uuid:
                recipient = SMSRecipient.objects.select_for_update().filter(
                    request_id=request_uuid,
                ).first()
        configured_sender = getattr(settings, 'HTTPSMS_FROM_NUMBER', '')
        sender_matches = True
        if configured_sender:
            try:
                sender_matches = normalize_phone_number(configured_sender) == owner
            except ValueError:
                sender_matches = False

        if (
            not recipient
            or recipient.phone_number != contact
            or not sender_matches
            or (recipient.provider_message_id and recipient.provider_message_id != message_id)
        ):
            logger.warning(
                'No SMS recipient matched signed httpSMS event type=%s',
                event_type,
            )
            return 'unmatched'

        recipient.provider_message_id = message_id
        recipient.save(update_fields=('provider_message_id', 'updated_at'))
        terminal_statuses = {'delivered', 'failed', 'expired'}
        if recipient.status not in terminal_statuses:
            recipient.status = target_status
            recipient.provider_status = event_type[:100]
            recipient.error_message = (
                str(data.get('error_message', ''))[:500]
                if target_status in ('failed', 'expired')
                else ''
            )
            recipient.save(update_fields=(
                'status',
                'provider_status',
                'error_message',
                'updated_at',
            ))
        webhook_event.processing_status = 'processed'
        webhook_event.save(update_fields=('processing_status',))
        refresh_campaign_status(recipient.campaign)
    return 'processed'


def refresh_campaign_status(campaign):
    statuses = list(campaign.recipients.values_list('status', flat=True))
    if not statuses:
        campaign.status = 'failed'
    elif any(status == 'pending' for status in statuses):
        campaign.status = 'sending'
    elif all(status == 'delivered' for status in statuses):
        campaign.status = 'delivered'
    elif all(status in ('failed', 'expired') for status in statuses):
        campaign.status = 'failed'
    elif any(status in ('failed', 'expired', 'unknown') for status in statuses):
        campaign.status = 'partial'
    else:
        campaign.status = 'accepted'

    if campaign.status != 'sending':
        campaign.completed_at = timezone.now()
        campaign.save(update_fields=('status', 'completed_at'))
    else:
        campaign.save(update_fields=('status',))
