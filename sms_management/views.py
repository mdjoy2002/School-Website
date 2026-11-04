import json
import logging
import uuid
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError
from django.contrib.auth.views import redirect_to_login
from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Prefetch, Q, Sum
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from students.models import Student

from .forms import SMSComposeForm
from .access import user_can_access_sms
from .models import SMSCampaign, SMSRecipient
from .services import (
    process_webhook_event,
    render_personalized_message,
    resolve_recipients,
    verify_webhook_token,
)
from .provider import (
    SMSGatewayError,
    check_balance as check_gateway_balance,
    refresh_campaign_status as refresh_gateway_campaign_status,
    refresh_recipient_report,
    submit_httpsms_recipient,
    submit_recipient,
)


logger = logging.getLogger(__name__)


def sms_admin_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
        if not request.user.is_active:
            raise PermissionDenied
        teacher = None
        try:
            teacher = request.user.teacher
        except ObjectDoesNotExist:
            pass
        if not user_can_access_sms(request.user, teacher):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapped


@sms_admin_required
def dashboard(request):
    if request.method == 'POST':
        form = SMSComposeForm(request.POST)
        if form.is_valid():
            recipients, excluded_count, duplicate_count = resolve_recipients(
                audience=form.cleaned_data['audience'],
                classes=form.cleaned_data.get('classes', ()),
                students=form.cleaned_data.get('selected_students', ()),
                teachers=form.cleaned_data.get('selected_teachers', ()),
                office_staff=form.cleaned_data.get('selected_office_staff', ()),
                test_number=form.cleaned_data.get('test_number', ''),
            )
            if not recipients:
                form.add_error(None, 'No valid phone numbers were found. Check the selected records and their mobile numbers.')
            else:
                campaign = _create_draft_campaign(
                    request,
                    form.cleaned_data,
                    recipients,
                    excluded_count,
                )
                gateway_type = form.cleaned_data.get('gateway', 'sms_net_bd')
                return render(
                    request,
                    'sms_management/confirm_send.html',
                    {
                        'campaign': campaign,
                        'recipients': campaign.recipients.all(),
                        'excluded_count': campaign.excluded_count,
                        'duplicate_count': duplicate_count,
                        'balance': request.session.get('sms_gateway_balance'),
                        'balance_required': gateway_type == 'sms_net_bd',
                        'bulk_content_id_ready': (
                            gateway_type != 'sms_net_bd'
                            or campaign.recipient_count <= 1
                            or bool(getattr(settings, 'SMS_GATEWAY_CONTENT_ID', ''))
                        ),
                    },
                )
    else:
        form = SMSComposeForm()

    recipient_type = request.GET.get('recipient_type', 'all')
    recipient_types = {'all', 'guardian', 'teacher', 'office_staff'}
    if recipient_type not in recipient_types:
        recipient_type = 'all'
    recipient_queryset = SMSRecipient.objects.all()
    campaigns_queryset = SMSCampaign.objects.annotate(
        pending_recipient_count=Count(
            'recipients',
            filter=Q(recipients__status='pending'),
        ),
    )
    if recipient_type != 'all':
        recipient_queryset = recipient_queryset.filter(recipient_type=recipient_type)
        campaigns_queryset = campaigns_queryset.filter(
            recipients__recipient_type=recipient_type,
        ).distinct()
    campaigns = campaigns_queryset.prefetch_related(
        Prefetch('recipients', queryset=recipient_queryset, to_attr='visible_recipients')
    )[:30]
    history_counts = {
        row['recipient_type']: row['total']
        for row in SMSRecipient.objects.values('recipient_type').annotate(total=Count('id'))
    }
    test_delivered = SMSCampaign.gateway_has_successful_test_sms('sms_net_bd') or SMSCampaign.gateway_has_successful_test_sms('httpsms')
    campaign_stats = SMSCampaign.objects.aggregate(
        total=Count('id'),
        recipients=Sum('recipient_count'),
    )
    recipient_stats = SMSRecipient.objects.aggregate(
        submitted=Count('id', filter=Q(status__in=('submitted', 'accepted'))),
        sent=Count('id', filter=Q(status__in=('sent', 'delivered'))),
        failed=Count('id', filter=Q(status='failed')),
        delivered=Count('id', filter=Q(status='delivered')),
        needs_attention=Count('id', filter=Q(status__in=('failed', 'expired', 'unknown', 'submitting'))),
    )
    return render(request, 'sms_management/dashboard.html', {
        'form': form,
        'selected_student_ids': request.POST.getlist('selected_students') if request.method == 'POST' else [],
        'campaigns': campaigns,
        'recipient_type_filter': recipient_type,
        'history_counts': history_counts,
        'visible_history_count': (
            SMSRecipient.objects.count()
            if recipient_type == 'all'
            else history_counts.get(recipient_type, 0)
        ),
        'test_delivered': test_delivered,
        'campaign_stats': campaign_stats,
        'recipient_stats': recipient_stats,
        'balance': request.session.get('sms_gateway_balance'),
        'api_configured': bool(
            getattr(settings, 'SMS_GATEWAY_API_KEY', '')
            or (
                getattr(settings, 'HTTPSMS_API_KEY', '')
                and (
                    getattr(settings, 'HTTPSMS_PHONE_NUMBER', '')
                    or getattr(settings, 'HTTPSMS_FROM_NUMBER', '')
                )
            )
        ),
        'sms_net_configured': bool(getattr(settings, 'SMS_GATEWAY_API_KEY', '')),
        'httpsms_configured': bool(
            getattr(settings, 'HTTPSMS_API_KEY', '')
            and (
                getattr(settings, 'HTTPSMS_PHONE_NUMBER', '')
                or getattr(settings, 'HTTPSMS_FROM_NUMBER', '')
            )
        ),
        'content_id_configured': bool(getattr(settings, 'SMS_GATEWAY_CONTENT_ID', '')),
    })


@sms_admin_required
def review_pending_campaign(request, campaign_id):
    campaign = get_object_or_404(
        SMSCampaign,
        pk=campaign_id,
        created_by=request.user,
        status='draft',
    )
    recipients = campaign.recipients.filter(
        status='pending',
        api_request_id='',
        provider_message_id__isnull=True,
    )
    if not recipients.exists():
        messages.info(request, 'এই campaign-এ পুনরায় পাঠানোর মতো কোনো pending SMS নেই।')
        return redirect('sms_management:dashboard')
    return render(
        request,
        'sms_management/confirm_send.html',
        {
            'campaign': campaign,
            'recipients': recipients,
            'excluded_count': campaign.excluded_count,
            'duplicate_count': 0,
            'balance': request.session.get('sms_gateway_balance'),
            'balance_required': campaign.gateway == 'sms_net_bd',
            'bulk_content_id_ready': (
                campaign.gateway != 'sms_net_bd'
                or recipients.count() <= 1
                or bool(getattr(settings, 'SMS_GATEWAY_CONTENT_ID', ''))
            ),
            'is_reviewing_pending': True,
        },
    )


@sms_admin_required
@require_POST
def delete_sent_recipient(request, campaign_id, recipient_id):
    recipient = get_object_or_404(
        SMSRecipient,
        pk=recipient_id,
        campaign_id=campaign_id,
    )
    recipient_type = request.POST.get('recipient_type', 'all')
    if recipient_type not in {'all', 'guardian', 'teacher', 'office_staff'}:
        recipient_type = 'all'
    campaign = recipient.campaign
    with transaction.atomic():
        recipient.delete()
        campaign.recipient_count = campaign.recipients.count()
        campaign.save(update_fields=('recipient_count',))
    messages.success(request, 'SMS history record was deleted.')
    return redirect(
        f'{reverse("sms_management:dashboard")}?recipient_type={recipient_type}'
    )


@sms_admin_required
def students_for_class(request):
    class_level = request.GET.get('class_level', '')
    if class_level not in dict(SMSComposeForm.base_fields['selected_class'].choices):
        return JsonResponse({'error': 'শ্রেণি নির্বাচনটি সঠিক নয়।'}, status=400)

    students = Student.objects.filter(
        current_class=class_level,
    ).order_by('class_roll', 'full_name')
    student_data = []
    for student in students:
        try:
            photo_url = student.photo.url if student.photo else ''
        except ValueError:
            photo_url = ''
        student_data.append({
            'id': student.pk,
            'name': student.full_name,
            'class_level': student.current_class,
            'roll': student.class_roll,
            'guardian': student.father_name or student.mother_name,
            'photo_url': photo_url,
        })
    return JsonResponse({'students': student_data})


def _create_draft_campaign(request, form_data, recipient_data, excluded_count):
    gateway_val = form_data.get('gateway', 'sms_net_bd')
    with transaction.atomic():
        campaign = SMSCampaign.objects.create(
            created_by=request.user,
            gateway=gateway_val,
            audience=form_data['audience'],
            title=form_data['title'],
            content=form_data['message'],
            scheduled_at=form_data.get('scheduled_at'),
            recipient_count=len(recipient_data),
            excluded_count=excluded_count,
        )
        for item in recipient_data:
            recipient = SMSRecipient.objects.create(
                campaign=campaign,
                recipient_type=item['recipient_type'],
                recipient_name=item['recipient_name'],
                phone_number=item['phone_number'],
                student_names=item['student_names'],
                message=render_personalized_message(
                    item['recipient_type'],
                    form_data['message'],
                    recipient_name=item['recipient_name'],
                    student_names=item['student_names'],
                ),
            )
            if item['student_ids']:
                recipient.students.set(item['student_ids'])
            if item['teacher_id']:
                recipient.teacher_id = item['teacher_id']
                recipient.save(update_fields=('teacher',))
            if item['office_staff_id']:
                recipient.office_staff_record_id = item['office_staff_id']
                recipient.save(update_fields=('office_staff_record',))
    return campaign


@sms_admin_required
@require_POST
def confirm_send(request, campaign_id):
    try:
        confirmation_token = uuid.UUID(request.POST.get('confirmation_token', ''))
    except (ValueError, AttributeError):
        messages.error(request, 'Invalid campaign confirmation. Please review the campaign again.')
        return redirect('sms_management:dashboard')

    campaign = get_object_or_404(
        SMSCampaign,
        pk=campaign_id,
        created_by=request.user,
        status='draft',
        confirmation_token=confirmation_token,
    )
    if request.POST.get('confirm_send') != 'yes':
        messages.error(request, 'Please explicitly confirm the recipient list and message before sending.')
        return redirect('sms_management:dashboard')

    # আপডেট করা চেক: মডেলে তৈরি করা হেল্পার মেথড ব্যবহার করে যাচাই করা হচ্ছে
    if campaign.audience != 'test' and not SMSCampaign.gateway_has_successful_test_sms(campaign.gateway):
        messages.error(
            request,
            'Bulk SMS is locked until a test SMS has a Sent, Delivered, or Accepted status on the selected gateway.',
        )
        return redirect('sms_management:dashboard')

    if (
        campaign.gateway == 'sms_net_bd'
        and campaign.recipient_count > 1
        and not getattr(settings, 'SMS_GATEWAY_CONTENT_ID', '')
    ):
        messages.error(
            request,
            'SMS_GATEWAY_CONTENT_ID must contain an approved content ID before a bulk campaign can be sent.',
        )
        return redirect('sms_management:dashboard')

    if campaign.gateway == 'sms_net_bd' and not getattr(settings, 'SMS_GATEWAY_API_KEY', ''):
        messages.error(request, 'SMS_GATEWAY_API_KEY is not configured in the server environment.')
        return redirect('sms_management:dashboard')
    
    if campaign.gateway == 'httpsms' and not (
        getattr(settings, 'HTTPSMS_API_KEY', '')
        and (
            getattr(settings, 'HTTPSMS_PHONE_NUMBER', '')
            or getattr(settings, 'HTTPSMS_FROM_NUMBER', '')
        )
    ):
        messages.error(
            request,
            'HTTPSMS_API_KEY and HTTPSMS_PHONE_NUMBER must be configured on the server.',
        )
        return redirect('sms_management:dashboard')

    with transaction.atomic():
        started = SMSCampaign.objects.filter(
            pk=campaign.pk,
            status='draft',
            confirmation_token=confirmation_token,
        ).update(status='sending', submitted_at=timezone.now())
        if not started:
            messages.error(request, 'This campaign has already been confirmed or is no longer available.')
            return redirect('sms_management:dashboard')

    campaign.refresh_from_db()
    try:
        for recipient in campaign.recipients.filter(
            status='pending',
            api_request_id='',
            provider_message_id__isnull=True,
        ).order_by('pk'):
            if campaign.gateway == 'httpsms':
                submit_httpsms_recipient(recipient)
            else:
                submit_recipient(recipient, campaign)
    except SMSGatewayError as exc:
        campaign.status = 'failed'
        campaign.completed_at = timezone.now()
        campaign.save(update_fields=('status', 'completed_at'))
        logger.error('SMS gateway configuration error for campaign=%s: %s', campaign.pk, exc)
        messages.error(request, str(exc))
        return redirect('sms_management:dashboard')

    refresh_gateway_campaign_status(campaign)
    submitted_count = campaign.recipients.filter(
        status__in=('submitted', 'accepted', 'sent', 'delivered'),
    ).count()
    failed_count = campaign.recipients.filter(status='failed').count()
    unknown_count = campaign.recipients.filter(status='unknown').count()

    if unknown_count:
        messages.warning(
            request,
            f'{submitted_count} SMS request(s) were submitted, {failed_count} failed, and '
            f'{unknown_count} have an unknown outcome. Do not retry unknown requests automatically.',
        )
    elif failed_count:
        messages.warning(
            request,
            f'{submitted_count} SMS request(s) were submitted and {failed_count} failed. '
            'A submitted request is not a delivery confirmation.',
        )
    else:
        if campaign.gateway == 'httpsms':
            messages.success(
                request,
                f'{submitted_count} SMS request(s) were accepted by httpSMS. '
                'Delivery status may update through the configured httpSMS webhook.',
            )
        else:
            messages.success(
                request,
                f'{submitted_count} SMS request(s) were submitted to SMS.NET.BD. '
                'Check each provider report for its latest status.',
            )
    return redirect('sms_management:dashboard')


@sms_admin_required
@require_POST
def check_balance(request):
    request.session.pop('sms_gateway_balance', None)
    try:
        request.session['sms_gateway_balance'] = check_gateway_balance()
    except SMSGatewayError as exc:
        logger.warning('SMS.NET.BD balance check failed: %s', exc)
        messages.error(request, str(exc))
    else:
        balance = request.session['sms_gateway_balance']
        messages.success(
            request,
            f"SMS.NET.BD account balance: {balance['amount']} (checked {balance['checked_at']}).",
        )
    return redirect('sms_management:dashboard')


@sms_admin_required
@require_POST
def refresh_report(request, campaign_id, recipient_id):
    recipient = get_object_or_404(
        SMSRecipient,
        pk=recipient_id,
        campaign_id=campaign_id,
    )
    try:
        report_message = refresh_recipient_report(recipient)
    except SMSGatewayError as exc:
        logger.warning(
            'SMS.NET.BD report check failed for campaign=%s recipient=%s: %s',
            campaign_id,
            recipient_id,
            exc,
        )
        messages.error(request, str(exc))
    else:
        refresh_gateway_campaign_status(recipient.campaign)
        messages.info(request, report_message)
    return redirect('sms_management:dashboard')


@csrf_exempt
@require_POST
def webhook(request):
    signing_key = getattr(settings, 'HTTPSMS_WEBHOOK_SIGNING_KEY', '')
    if not verify_webhook_token(request.headers.get('Authorization', ''), signing_key):
        logger.warning('Rejected httpSMS webhook with invalid authorization')
        return HttpResponseForbidden(
            json.dumps({'status': 'error', 'message': 'Invalid webhook authorization.'}),
            content_type='application/json',
        )

    if len(request.body) > 65536:
        return HttpResponse(
            json.dumps({'status': 'error', 'message': 'Payload too large.'}),
            status=413,
            content_type='application/json',
        )
    try:
        event = json.loads(request.body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return HttpResponseBadRequest(
            json.dumps({'status': 'error', 'message': 'Invalid JSON.'}),
            content_type='application/json',
        )

    if not isinstance(event, dict):
        return HttpResponseBadRequest(
            json.dumps({'status': 'error', 'message': 'Invalid event.'}),
            content_type='application/json',
        )

    header_event_type = request.headers.get('X-Event-Type', '')
    if (
        not isinstance(event.get('id'), str)
        or not event['id'].strip()
        or len(event['id']) > 100
        or not isinstance(event.get('type'), str)
        or not event['type'].strip()
        or not isinstance(event.get('data'), dict)
        or not header_event_type
        or header_event_type != event['type']
    ):
        return HttpResponseBadRequest(
            json.dumps({'status': 'error', 'message': 'Missing or inconsistent event fields.'}),
            content_type='application/json',
        )

    if event['type'] in {
        'message.phone.sent',
        'message.phone.delivered',
        'message.send.failed',
        'message.send.expired',
    }:
        data = event['data']
        message_id = data.get('id') or data.get('message_id')
        if not all(
            isinstance(value, str) and value.strip()
            for value in (message_id, data.get('contact'), data.get('owner'))
        ) or len(message_id) > 100:
            return HttpResponseBadRequest(
                json.dumps({'status': 'error', 'message': 'Missing required message fields.'}),
                content_type='application/json',
            )

    try:
        result = process_webhook_event(event)
    except ValueError:
        return HttpResponseBadRequest(
            json.dumps({'status': 'error', 'message': 'Invalid webhook payload.'}),
            content_type='application/json',
        )
    except DatabaseError:
        logger.error('Database error while processing signed httpSMS webhook')
        return HttpResponse(
            json.dumps({'status': 'error', 'message': 'Temporary processing failure.'}),
            status=503,
            content_type='application/json',
        )

    return HttpResponse(
        json.dumps({'status': 'success', 'result': result}),
        status=200,
        content_type='application/json',
    )