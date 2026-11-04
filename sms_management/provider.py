import logging
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import SMSCampaign, SMSRecipient
from .services import normalize_phone_number


logger = logging.getLogger(__name__)

SEND_URL = 'https://api.sms.net.bd/sendsms'
REPORT_URL = 'https://api.sms.net.bd/report/request/'
BALANCE_URL = 'https://api.sms.net.bd/user/balance/'
REQUEST_TIMEOUT = (5, 20)

API_ERROR_MESSAGES = {
    0: 'Request successfully submitted.',
    400: 'A required field is missing or invalid.',
    403: 'The SMS account does not have permission for this request.',
    405: 'SMS account authorization failed. Check the API key.',
    404: 'The requested SMS.NET.BD resource was not found.',
    409: 'SMS.NET.BD reported an unknown server error.',
    410: 'The SMS account has expired.',
    411: 'The reseller account has expired or is suspended.',
    412: 'The scheduled send date or time is invalid.',
    413: 'The configured Sender ID is invalid or not approved.',
    414: 'The SMS message is empty.',
    415: 'The SMS message is too long.',
    416: 'No valid Bangladesh phone number was found.',
    417: 'The SMS account has insufficient balance.',
    420: 'The message was blocked by the provider.',
    421: 'Until the first balance recharge, SMS can only be sent to the phone number registered with SMS.NET.BD.',
}


class SMSGatewayError(Exception):
    def __init__(self, message, error_code=None):
        super().__init__(message)
        self.error_code = error_code


def _api_key():
    api_key = getattr(settings, 'SMS_GATEWAY_API_KEY', '')
    if not api_key:
        raise SMSGatewayError('SMS_GATEWAY_API_KEY is not configured on the server.')
    return api_key


def _response_data(response):
    try:
        value = response.json()
    except (ValueError, requests.exceptions.JSONDecodeError):
        return {'body': response.text[:20000]}
    return value if isinstance(value, (dict, list)) else {'response': value}


def _error_code(payload):
    if isinstance(payload, dict):
        value = payload.get('error', payload.get('error_code'))
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None
    return None


def error_message(error_code, fallback='The SMS provider rejected the request.'):
    return API_ERROR_MESSAGES.get(error_code, fallback)


def _request_id(payload):
    if not isinstance(payload, dict):
        return ''
    for candidate in (payload, payload.get('data')):
        if isinstance(candidate, dict):
            value = candidate.get('request_id') or candidate.get('requestId')
            if value is not None and str(value).strip():
                return str(value).strip()[:100]
    return ''


def submit_recipient(recipient, campaign):
    # Campaign ba gateway selection check korbe kon API-te pathabe
    gateway = getattr(campaign, 'gateway', 'smsnetbd')
    if gateway == 'httpsms' or getattr(settings, 'SMS_DEFAULT_GATEWAY', '') == 'httpsms':
        return submit_httpsms_recipient(recipient)

    api_key = _api_key()
    if recipient.status != 'pending':
        return

    with transaction.atomic():
        claimed = SMSRecipient.objects.filter(
            pk=recipient.pk,
            status='pending',
        ).update(status='submitting')
        if not claimed:
            return
    recipient.status = 'submitting'

    payload = {
        'api_key': api_key,
        'msg': recipient.message,
        'to': recipient.phone_number.removeprefix('+'),
    }
    
    # Sender ID bad dewa hoyeche jate 413 error na ase
    content_id = getattr(settings, 'SMS_GATEWAY_CONTENT_ID', '')
    if content_id:
        payload['content_id'] = content_id
    if campaign.scheduled_at:
        payload['schedule'] = timezone.localtime(campaign.scheduled_at).strftime('%Y-%m-%d %H:%M:%S')

    try:
        response = requests.post(
            SEND_URL,
            data=payload,
            headers={'Accept': 'application/json'},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException:
        recipient.status = 'unknown'
        recipient.error_message = (
            'No reliable response from SMS.NET.BD. The outcome is unknown; do not retry automatically.'
        )
        recipient.save(update_fields=('status', 'error_message', 'updated_at'))
        logger.warning(
            'SMS.NET.BD outcome unknown for campaign=%s recipient=%s',
            campaign.pk,
            recipient.pk,
        )
        return

    response_data = _response_data(response)
    recipient.api_response = response_data
    recipient.api_error_code = _error_code(response_data)
    recipient.api_request_id = _request_id(response_data)

    if not response.ok:
        if response.status_code >= 500:
            recipient.status = 'unknown'
            recipient.error_message = (
                f'SMS.NET.BD returned HTTP {response.status_code}; the outcome is unknown. '
                'Do not retry automatically.'
            )
        else:
            recipient.status = 'failed'
            recipient.error_message = error_message(
                recipient.api_error_code,
                f'SMS.NET.BD rejected the request (HTTP {response.status_code}).',
            )
    elif recipient.api_error_code != 0:
        recipient.status = 'failed'
        recipient.error_message = error_message(recipient.api_error_code)
    elif not recipient.api_request_id:
        recipient.status = 'unknown'
        recipient.error_message = (
            'SMS.NET.BD accepted the request but returned no request ID. '
            'The outcome is unknown; do not retry automatically.'
        )
    else:
        recipient.status = 'submitted'
        recipient.submitted_at = timezone.now()
        recipient.error_message = ''

    recipient.save(update_fields=(
        'api_request_id',
        'api_error_code',
        'api_response',
        'status',
        'submitted_at',
        'error_message',
        'updated_at',
    ))


def send_sms_via_httpsms(phone_number, message, request_id=None):
    api_key = getattr(settings, 'HTTPSMS_API_KEY', '')
    if not api_key:
        raise SMSGatewayError('HTTPSMS_API_KEY is not configured on the server.')

    sender_number = (
        getattr(settings, 'HTTPSMS_PHONE_NUMBER', '')
        or getattr(settings, 'HTTPSMS_FROM_NUMBER', '')
    )
    try:
        if sender_number:
            sender_number = normalize_phone_number(sender_number)
        recipient_number = normalize_phone_number(phone_number)
    except ValueError as exc:
        raise SMSGatewayError(
            'Recipient must be a valid Bangladesh mobile number.'
        ) from exc

    payload = {
        'to': recipient_number,
        'content': message,
    }
    if sender_number:
        payload['from'] = sender_number
    if request_id:
        payload['request_id'] = str(request_id)

    try:
        return requests.post(
            'https://api.httpsms.com/v1/messages/send',
            headers={
                'x-api-key': api_key,
                'Accept': 'application/json',
            },
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise SMSGatewayError(
            'No reliable response from httpSMS. The outcome is unknown; do not retry automatically.'
        ) from exc


def submit_httpsms_recipient(recipient):
    if recipient.status != 'pending':
        return

    with transaction.atomic():
        claimed = SMSRecipient.objects.filter(
            pk=recipient.pk,
            status='pending',
        ).update(status='submitting')
        if not claimed:
            return

    try:
        # Check if recipient model has request_id or api_request_id
        req_id = getattr(recipient, 'request_id', getattr(recipient, 'api_request_id', None))
        response = send_sms_via_httpsms(
            recipient.phone_number,
            recipient.message,
            request_id=req_id,
        )
    except SMSGatewayError as exc:
        recipient.status = 'unknown' if 'unknown' in str(exc).lower() else 'failed'
        recipient.error_message = str(exc)[:500]
        recipient.save(update_fields=('status', 'error_message', 'updated_at'))
        return

    response_data = _response_data(response)
    recipient.api_response = response_data
    recipient.api_error_code = _error_code(response_data)
    if not response.ok:
        recipient.status = 'unknown' if response.status_code >= 500 else 'failed'
        recipient.error_message = (
            'httpSMS returned an uncertain server error; do not retry automatically.'
            if response.status_code >= 500
            else f'httpSMS rejected the request (HTTP {response.status_code}).'
        )
    else:
        try:
            data = response_data['data']
            provider_message_id = data['id']
        except (KeyError, TypeError):
            provider_message_id = None
        if provider_message_id is None:
            recipient.status = 'unknown'
            recipient.error_message = (
                'httpSMS returned no message ID. The outcome is unknown; do not retry automatically.'
            )
        else:
            recipient.provider_message_id = str(provider_message_id)
            recipient.provider_status = str(response_data.get('status', 'accepted'))[:100]
            recipient.status = 'accepted'
            recipient.submitted_at = timezone.now()
            recipient.error_message = ''

    recipient.save(update_fields=(
        'provider_message_id',
        'provider_status',
        'api_error_code',
        'api_response',
        'status',
        'submitted_at',
        'error_message',
        'updated_at',
    ))


def _report_item(payload, phone_number):
    if not isinstance(payload, dict):
        return {}
    data = payload.get('data')
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and _report_number_matches(item, phone_number):
                return item
        return {}
    if not isinstance(data, dict):
        return {}
    for key in ('recipients', 'messages', 'report'):
        items = data.get(key)
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and _report_number_matches(item, phone_number):
                    return item
            return {}
    return data


def _report_number_matches(item, phone_number):
    reported_number = item.get('number', item.get('to', item.get('phone_number')))
    if not reported_number:
        return False
    try:
        return normalize_phone_number(reported_number) == phone_number
    except ValueError:
        return False


def _decimal_value(data, keys):
    if not isinstance(data, dict):
        return None
    for key in keys:
        if data.get(key) is not None:
            try:
                return Decimal(str(data[key]))
            except (InvalidOperation, TypeError, ValueError):
                return None
    return None


def _apply_report(recipient, payload):
    item = _report_item(payload, recipient.phone_number)
    raw_status = item.get('status') or item.get('sms_status') or item.get('delivery_status')
    normalized_status = str(raw_status or '').strip().lower()
    item_error_code = _error_code(item)
    if item_error_code is not None:
        recipient.api_error_code = item_error_code
    else:
        recipient.api_error_code = _error_code(payload)
    status_map = {
        'submitted': 'submitted',
        'pending': 'submitted',
        'queued': 'submitted',
        'processing': 'submitted',
        'sent': 'sent',
        'delivered': 'delivered',
        'failed': 'failed',
        'expired': 'failed',
    }
    if normalized_status in status_map:
        recipient.status = status_map[normalized_status]
        recipient.provider_status = str(raw_status)[:100]
        if recipient.status in ('sent', 'delivered') and not recipient.sent_at:
            recipient.sent_at = timezone.now()
        if recipient.status == 'failed':
            recipient.error_message = error_message(
                item_error_code,
                str(item.get('message') or item.get('error') or '')[:500],
            )
    charge = _decimal_value(item, ('charge', 'sms_charge', 'cost', 'amount'))
    if charge is not None:
        recipient.sms_charge = charge
    recipient.api_response = payload
    recipient.api_error_code = _error_code(payload)
    recipient.save(update_fields=(
        'status',
        'provider_status',
        'sent_at',
        'error_message',
        'sms_charge',
        'api_response',
        'api_error_code',
        'updated_at',
    ))
    return normalized_status


def refresh_recipient_report(recipient):
    if not recipient.api_request_id:
        raise SMSGatewayError('This recipient has no SMS.NET.BD request ID to report.')
    api_key = _api_key()
    url = f'{REPORT_URL}{quote(recipient.api_request_id, safe="")}/'
    try:
        response = requests.post(
            url,
            data={'api_key': api_key},
            headers={'Accept': 'application/json'},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise SMSGatewayError(
            'Could not reach SMS.NET.BD to check the report. The recipient status was not changed.'
        ) from exc

    payload = _response_data(response)
    if not response.ok:
        code = _error_code(payload)
        raise SMSGatewayError(
            error_message(
                code,
                f'SMS.NET.BD report request failed (HTTP {response.status_code}).',
            ),
            code,
        )
    code = _error_code(payload)
    if code != 0:
        raise SMSGatewayError(error_message(code, 'SMS.NET.BD could not return this report.'), code)
    status = _apply_report(recipient, payload)
    if not status:
        return 'The report was saved, but it did not include a recognized recipient status.'
    return f'Provider report status: {status}.'


def check_balance():
    api_key = _api_key()
    try:
        response = requests.post(
            BALANCE_URL,
            data={'api_key': api_key},
            headers={'Accept': 'application/json'},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise SMSGatewayError('Could not reach SMS.NET.BD to check the account balance.') from exc

    payload = _response_data(response)
    if not response.ok:
        code = _error_code(payload)
        raise SMSGatewayError(
            error_message(
                code,
                f'SMS.NET.BD balance request failed (HTTP {response.status_code}).',
            ),
            code,
        )
    code = _error_code(payload)
    if code != 0:
        raise SMSGatewayError(error_message(code, 'SMS.NET.BD could not return the account balance.'), code)

    data = payload.get('data') if isinstance(payload, dict) else None
    balance = _decimal_value(data, ('balance', 'available_balance', 'current_balance'))
    if balance is None:
        balance = _decimal_value(payload, ('balance', 'available_balance', 'current_balance'))
    if balance is None:
        raise SMSGatewayError('SMS.NET.BD returned a successful response without a readable balance.')
    return {
        'amount': str(balance),
        'checked_at': timezone.localtime().isoformat(timespec='minutes'),
    }


def refresh_campaign_status(campaign):
    statuses = list(campaign.recipients.values_list('status', flat=True))
    successful = {'submitted', 'sent', 'delivered', 'accepted'}
    incomplete = {'pending', 'submitting'}
    if not statuses:
        campaign.status = 'failed'
    elif any(status in incomplete for status in statuses):
        campaign.status = 'sending'
    elif all(status == 'failed' for status in statuses):
        campaign.status = 'failed'
    elif any(status in ('failed', 'unknown', 'expired') for status in statuses):
        campaign.status = 'partial' if any(status in successful for status in statuses) else 'unknown'
    elif all(status == 'delivered' for status in statuses):
        campaign.status = 'delivered'
    elif any(status in ('sent', 'delivered') for status in statuses):
        campaign.status = 'sent'
    elif all(status == 'accepted' for status in statuses):
        campaign.status = 'accepted'
    else:
        campaign.status = 'submitted'

    if campaign.status != 'sending':
        campaign.completed_at = timezone.now()
    campaign.save(update_fields=('status', 'completed_at'))