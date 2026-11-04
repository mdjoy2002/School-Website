import base64
import hashlib
import hmac
import json
import time
from datetime import timedelta
from unittest.mock import Mock, patch

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from requests.exceptions import Timeout

from main_app.models import Teacher as SchoolStaffRecord
from myteacher.models import Teacher
from students.models import Student

from .forms import SMSComposeForm
from .models import SMSAccessSettings, SMSCampaign, SMSRecipient, SMSWebhookEvent
from .services import (
    HTTPSMS_SEND_URL,
    SCHOOL_SMS_PREFIX,
    _render_message,
    normalize_phone_number,
    process_webhook_event,
    render_personalized_message,
    resolve_recipients,
    send_sms,
    verify_webhook_token,
)
from .provider import (
    API_ERROR_MESSAGES,
    BALANCE_URL,
    REPORT_URL,
    SEND_URL,
    SMSGatewayError,
    check_balance,
    error_message,
    refresh_recipient_report,
    send_sms_via_httpsms,
    submit_httpsms_recipient,
    submit_recipient,
)


@override_settings(HTTPSMS_FROM_NUMBER='')
class SMSManagementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='sms-admin',
            password='test-password',
            is_staff=True,
        )
        permission = Permission.objects.get(codename='access_sms_dashboard')
        self.user.user_permissions.add(permission)
        self.student = Student.objects.create(
            photo='',
            full_name='Rahim Ahmed',
            father_name='Kamal Ahmed',
            mother_name='Asha Ahmed',
            student_id='T100001',
            current_class='6',
            class_roll=1,
            mobile_num='01700000001',
        )

    def test_normalizes_bangladesh_local_number_to_e164(self):
        self.assertEqual(normalize_phone_number('01700-000001'), '+8801700000001')

    def test_normalizes_bangla_digits_and_rejects_non_bangladesh_numbers(self):
        self.assertEqual(normalize_phone_number('০১৭০০০০০০০১'), '+8801700000001')
        with self.assertRaises(ValueError):
            normalize_phone_number('+14155550123')
        with self.assertRaises(ValueError):
            normalize_phone_number('01000000000')

    def test_class_guardians_are_deduplicated_by_phone(self):
        Student.objects.create(
            photo='',
            full_name='Karim Ahmed',
            father_name='Kamal Ahmed',
            mother_name='Asha Ahmed',
            student_id='T100002',
            current_class='6',
            class_roll=2,
            mobile_num='01700000001',
        )

        recipients, excluded, duplicates = resolve_recipients(
            'class_guardians',
            classes=['6'],
        )

        self.assertEqual(len(recipients), 1)
        self.assertEqual(recipients[0]['student_names'], ['Rahim Ahmed', 'Karim Ahmed'])
        self.assertEqual(excluded, 0)
        self.assertEqual(duplicates, 1)

    def test_personalized_templates_use_recipient_names_and_neutral_teacher_salutation(self):
        guardian_message = render_personalized_message(
            'guardian',
            'আগামীকাল ছুটি।',
            student_names=['রহিম', 'করিম'],
        )
        teacher_message = render_personalized_message(
            'teacher',
            'আগামীকাল সভা।',
            recipient_name='শিক্ষক',
        )
        staff_message = render_personalized_message(
            'office_staff',
            'আগামীকাল সভা।',
            recipient_name='কর্মচারী',
        )

        self.assertIn('রহিম, করিম-এর জন্য বিশেষ বিজ্ঞপ্তি: আগামীকাল ছুটি।', guardian_message)
        self.assertIn('শ্রদ্ধেয় শিক্ষক, আগামীকাল সভা।', teacher_message)
        self.assertNotIn('স্যার/ম্যাডাম', teacher_message)
        self.assertIn('প্রিয় কর্মচারী,', staff_message)
        self.assertIn('মোঃ সেলিম সরদার', staff_message)

    def test_everyone_deduplicates_by_guardian_teacher_staff_priority(self):
        second_student = Student.objects.create(
            photo='',
            full_name='Karim Ahmed',
            father_name='Kamal Ahmed',
            mother_name='Asha Ahmed',
            student_id='T100002',
            current_class='6',
            class_roll=2,
            mobile_num='01700000001',
        )
        guardian_collision_teacher = Teacher.objects.create(
            user=get_user_model().objects.create_user(username='sms-overlap-teacher'),
            teacher_id='T-OVERLAP',
            teacher_name='Guardian overlap teacher',
            designation='Assistant Teacher',
            mobile='01700000001',
            email='overlap-teacher@example.com',
            teacher_img='',
        )
        unique_teacher = Teacher.objects.create(
            user=get_user_model().objects.create_user(username='sms-unique-teacher'),
            teacher_id='T-UNIQUE',
            teacher_name='Unique teacher',
            designation='Assistant Teacher',
            mobile='01700000003',
            email='unique-teacher@example.com',
            teacher_img='',
        )
        SchoolStaffRecord.objects.create(
            teacher_type='STAFF',
            name='Teacher overlap staff',
            image='',
            phone='01700000003',
        )
        unique_staff = SchoolStaffRecord.objects.create(
            teacher_type='STAFF',
            name='Unique staff',
            image='',
            phone='01700000004',
        )

        recipients, excluded, duplicates = resolve_recipients('everyone')
        by_phone = {recipient['phone_number']: recipient for recipient in recipients}

        self.assertEqual(excluded, 0)
        self.assertEqual(duplicates, 3)
        self.assertEqual(set(by_phone), {
            '+8801700000001',
            '+8801700000003',
            '+8801700000004',
        })
        self.assertEqual(by_phone['+8801700000001']['recipient_type'], 'guardian')
        self.assertEqual(
            by_phone['+8801700000001']['student_names'],
            [self.student.full_name, second_student.full_name],
        )
        self.assertEqual(by_phone['+8801700000003']['recipient_type'], 'teacher')
        self.assertEqual(by_phone['+8801700000003']['teacher_id'], unique_teacher.pk)
        self.assertNotEqual(
            by_phone['+8801700000003']['teacher_id'],
            guardian_collision_teacher.pk,
        )
        self.assertEqual(by_phone['+8801700000004']['recipient_type'], 'office_staff')
        self.assertEqual(by_phone['+8801700000004']['office_staff_id'], unique_staff.pk)

    def test_everyone_draft_previews_each_personalized_message(self):
        teacher = Teacher.objects.create(
            user=get_user_model().objects.create_user(username='sms-preview-teacher'),
            teacher_id='T-PREVIEW',
            teacher_name='Preview teacher',
            designation='Assistant Teacher',
            mobile='01700000002',
            email='preview-teacher@example.com',
            teacher_img='',
        )
        staff = SchoolStaffRecord.objects.create(
            teacher_type='STAFF',
            name='Preview staff',
            image='',
            phone='01700000003',
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('sms_management:dashboard'),
            {
                'gateway': 'sms_net_bd',
                'audience': 'everyone',
                'title': 'Everyone notice',
                'message': 'আগামীকাল সভা।',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.student.full_name)
        self.assertContains(response, teacher.teacher_name)
        self.assertContains(response, staff.name)
        self.assertContains(response, 'প্রিয় অভিভাবক')
        self.assertContains(response, 'শ্রদ্ধেয় Preview teacher')
        self.assertContains(response, 'প্রিয় Preview staff')
        campaign = SMSCampaign.objects.get(title='Everyone notice')
        self.assertEqual(campaign.recipient_count, 3)
        self.assertEqual(campaign.recipients.filter(status='pending').count(), 3)
        self.assertEqual(
            campaign.recipients.get(recipient_type='office_staff').office_staff_record_id,
            staff.pk,
        )

    def test_selected_office_staff_only_creates_individual_recipient_previews(self):
        selected_staff = SchoolStaffRecord.objects.create(
            teacher_type='STAFF',
            name='Selected staff',
            image='',
            phone='01700000005',
        )
        other_staff = SchoolStaffRecord.objects.create(
            teacher_type='STAFF',
            name='Other staff',
            image='',
            phone='01700000006',
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('sms_management:dashboard'),
            {
                'gateway': 'sms_net_bd',
                'audience': 'selected_office_staff',
                'title': 'Staff notice',
                'message': 'আগামীকাল সভা।',
                'selected_office_staff': [str(selected_staff.pk)],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, selected_staff.name)
        self.assertNotContains(response, other_staff.name)
        self.assertContains(response, f'প্রিয় {selected_staff.name},')
        campaign = SMSCampaign.objects.get(title='Staff notice')
        recipients = list(campaign.recipients.all())
        self.assertEqual(len(recipients), 1)
        self.assertEqual(recipients[0].office_staff_record_id, selected_staff.pk)
        self.assertEqual(recipients[0].phone_number, '+8801700000005')

    def test_selected_office_staff_requires_an_explicit_selection(self):
        form = SMSComposeForm(data={
            'gateway': 'sms_net_bd',
            'audience': 'selected_office_staff',
            'title': 'Staff notice',
            'message': 'আগামীকাল সভা।',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('selected_office_staff', form.errors)

    def test_selected_teacher_is_presented_as_individually_selectable_checkbox(self):
        teacher_user = get_user_model().objects.create_user(
            username='individual-sms-teacher',
            password='test-password',
        )
        teacher = Teacher.objects.create(
            user=teacher_user,
            teacher_id='T-INDIVIDUAL',
            teacher_name='Individual teacher',
            designation='Assistant Teacher',
            mobile='01800000008',
            email='individual-sms-teacher@example.com',
            teacher_img='',
        )
        form = SMSComposeForm()

        self.assertIsInstance(
            form.fields['selected_teachers'].widget,
            forms.CheckboxSelectMultiple,
        )
        rendered_options = str(form['selected_teachers'])
        self.assertIn('type="checkbox"', rendered_options)
        self.assertIn(f'value="{teacher.pk}"', rendered_options)
        self.assertIn(teacher.teacher_name, rendered_options)

    def test_single_selected_teacher_creates_only_that_teacher_sms(self):
        selected_user = get_user_model().objects.create_user(username='sms-selected-teacher')
        other_user = get_user_model().objects.create_user(username='sms-unselected-teacher')
        selected_teacher = Teacher.objects.create(
            user=selected_user,
            teacher_id='T-SELECTED',
            teacher_name='Selected teacher',
            designation='Assistant Teacher',
            mobile='01800000009',
            email='sms-selected@example.com',
            teacher_img='',
        )
        other_teacher = Teacher.objects.create(
            user=other_user,
            teacher_id='T-UNSELECTED',
            teacher_name='Unselected teacher',
            designation='Assistant Teacher',
            mobile='01800000010',
            email='sms-unselected@example.com',
            teacher_img='',
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('sms_management:dashboard'),
            {
                'gateway': 'sms_net_bd',
                'audience': 'selected_teachers',
                'title': 'Individual teacher notice',
                'message': 'আগামীকাল সভা।',
                'selected_teachers': [str(selected_teacher.pk)],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, selected_teacher.teacher_name)
        self.assertNotContains(response, other_teacher.teacher_name)
        recipients = list(SMSRecipient.objects.all())
        self.assertEqual(len(recipients), 1)
        self.assertEqual(recipients[0].teacher_id, selected_teacher.pk)
        self.assertEqual(recipients[0].phone_number, '+8801800000009')

    def test_campaign_links_every_student_for_a_deduplicated_guardian(self):
        second_student = Student.objects.create(
            photo='',
            full_name='Karim Ahmed',
            father_name='Kamal Ahmed',
            mother_name='Asha Ahmed',
            student_id='T100002',
            current_class='6',
            class_roll=2,
            mobile_num='01700000001',
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('sms_management:dashboard'),
            {
                'gateway': 'sms_net_bd',
                'audience': 'selected_guardians',
                'title': 'Class notice',
                'message': 'আগামীকাল ছুটি।',
                'selected_class': '6',
                'selected_students': [str(self.student.pk), str(second_student.pk)],
            },
        )

        self.assertEqual(response.status_code, 200)
        recipient = SMSRecipient.objects.get()
        self.assertEqual(recipient.students.count(), 2)
        self.assertEqual(recipient.campaign.recipient_count, 1)

    def test_test_audience_uses_only_manual_number(self):
        recipients, _, _ = resolve_recipients('test', test_number='01700000009')

        self.assertEqual(len(recipients), 1)
        self.assertEqual(recipients[0]['phone_number'], '+8801700000009')
        self.assertEqual(recipients[0]['recipient_type'], 'test')

    def test_outgoing_message_includes_school_name_and_bangla_content(self):
        message = _render_message('প্রিয় {name}, আগামীকাল ছুটি।', 'করিম', ['রহিম'])

        self.assertEqual(
            message,
            f'{SCHOOL_SMS_PREFIX}\nপ্রিয় করিম, আগামীকাল ছুটি।',
        )

    def test_class_student_list_returns_student_name_and_photo(self):
        self.student.photo = 'students/rahim.jpg'
        self.student.save(update_fields=['photo'])
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('sms_management:students_for_class'),
            {'class_level': '6'},
        )

        self.assertEqual(response.status_code, 200)
        student_data = response.json()['students']
        self.assertEqual(len(student_data), 1)
        self.assertEqual(student_data[0]['name'], self.student.full_name)
        self.assertTrue(student_data[0]['photo_url'].endswith(self.student.photo.name))

    def test_class_student_list_rejects_invalid_class(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('sms_management:students_for_class'),
            {'class_level': '11'},
        )

        self.assertEqual(response.status_code, 400)

    def test_selected_guardian_must_match_selected_class(self):
        form = SMSComposeForm(data={
            'gateway': 'sms_net_bd',
            'audience': 'selected_guardians',
            'message': 'আগামীকাল ছুটি।',
            'selected_class': '7',
            'selected_students': [str(self.student.pk)],
        })

        self.assertFalse(form.is_valid())
        self.assertIn('selected_students', form.errors)

    def test_dashboard_requires_sms_permission(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('sms_management:dashboard'))
        self.assertEqual(response.status_code, 200)

        other_staff = get_user_model().objects.create_user(
            username='other-staff',
            password='test-password',
            is_staff=True,
        )
        self.client.force_login(other_staff)
        self.assertEqual(self.client.get(reverse('sms_management:dashboard')).status_code, 403)

    def test_admin_can_grant_sms_access_to_selected_teachers_only(self):
        selected_user = get_user_model().objects.create_user(
            username='selected-sms-access',
            password='test-password',
        )
        selected_teacher = Teacher.objects.create(
            user=selected_user,
            teacher_id='T-SELECTED-SMS-ACCESS',
            teacher_name='Selected SMS teacher',
            designation='Assistant Teacher',
            mobile='01800000007',
            email='selected-sms-access@example.com',
            teacher_img='teachers/selected-sms-access.png',
        )
        unselected_user = get_user_model().objects.create_user(
            username='unselected-sms-access',
            password='test-password',
        )
        Teacher.objects.create(
            user=unselected_user,
            teacher_id='T-UNSELECTED-SMS-ACCESS',
            teacher_name='Unselected SMS teacher',
            designation='Assistant Teacher',
            mobile='01800000011',
            email='unselected-sms-access@example.com',
            teacher_img='teachers/unselected-sms-access.png',
        )
        superuser = get_user_model().objects.create_superuser(
            username='sms-setting-admin',
            email='sms-setting-admin@example.com',
            password='test-password',
        )
        self.client.force_login(superuser)

        change_url = reverse(
            'admin:sms_management_smsaccesssettings_change',
            args=(1,),
        )
        settings_response = self.client.get(change_url)
        self.assertEqual(settings_response.status_code, 200)
        self.assertContains(settings_response, 'SMS Management ব্যবহারের অনুমতিপ্রাপ্ত শিক্ষক')
        self.assertContains(settings_response, selected_teacher.teacher_name)

        saved = self.client.post(
            change_url,
            {
                'authorized_teachers': [str(selected_teacher.pk)],
                '_save': 'Save',
            },
        )
        self.assertTrue(
            SMSAccessSettings.objects.get(pk=1).authorized_teachers.filter(
                pk=selected_teacher.pk,
            ).exists()
        )
        self.assertEqual(saved.status_code, 302)

        self.client.force_login(selected_user)
        self.assertEqual(
            self.client.get(reverse('sms_management:dashboard')).status_code,
            200,
        )
        self.assertContains(
            self.client.get(reverse('sms_management:dashboard')),
            reverse('myteacher:dashboard'),
        )
        self.assertContains(
            self.client.get(reverse('myteacher:dashboard')),
            reverse('sms_management:dashboard'),
        )

        self.client.force_login(unselected_user)
        self.assertEqual(
            self.client.get(reverse('sms_management:dashboard')).status_code,
            403,
        )
        self.assertNotContains(
            self.client.get(reverse('myteacher:dashboard')),
            reverse('sms_management:dashboard'),
        )

    def test_sms_access_setting_is_visible_only_to_superusers_in_admin(self):
        superuser = get_user_model().objects.create_superuser(
            username='sms-setting-view-admin',
            email='sms-setting-view-admin@example.com',
            password='test-password',
        )
        self.client.force_login(superuser)
        response = self.client.get(
            reverse('admin:sms_management_smsaccesssettings_changelist')
        )
        self.assertEqual(response.status_code, 200)

        self.client.force_login(self.user)
        response = self.client.get(
            reverse('admin:sms_management_smsaccesssettings_changelist')
        )
        self.assertEqual(response.status_code, 403)

    def test_draft_campaign_can_be_reopened_to_review_only_unsent_pending_recipients(self):
        campaign = SMSCampaign.objects.create(
            created_by=self.user,
            audience='all_guardians',
            title='Pending notice',
            content='আগামীকাল ছুটি।',
            recipient_count=1,
        )
        recipient = SMSRecipient.objects.create(
            campaign=campaign,
            recipient_type='guardian',
            recipient_name='Guardian',
            phone_number='+8801700000011',
            message='Guardian notice',
        )
        self.client.force_login(self.user)

        with patch('sms_management.provider.requests.post') as post:
            response = self.client.get(
                reverse('sms_management:review_pending_campaign', args=(campaign.pk,))
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pending SMS পুনরায় যাচাই করুন')
        self.assertContains(response, recipient.message)
        post.assert_not_called()

    def test_pending_review_excludes_any_recipient_with_a_provider_identifier(self):
        campaign = SMSCampaign.objects.create(
            created_by=self.user,
            audience='all_guardians',
            title='Uncertain notice',
            content='Notice',
            recipient_count=1,
        )
        SMSRecipient.objects.create(
            campaign=campaign,
            recipient_type='guardian',
            recipient_name='Guardian',
            phone_number='+8801700000012',
            message='Notice',
            api_request_id='provider-request-123',
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('sms_management:review_pending_campaign', args=(campaign.pk,))
        )

        self.assertEqual(response.status_code, 302)

    def test_sms_history_recipient_can_be_deleted_with_post_and_campaign_count_is_updated(self):
        campaign = SMSCampaign.objects.create(
            created_by=self.user,
            audience='all_guardians',
            title='Sent notice',
            content='Notice',
            status='sent',
            recipient_count=1,
        )
        recipient = SMSRecipient.objects.create(
            campaign=campaign,
            recipient_type='guardian',
            recipient_name='Guardian',
            phone_number='+8801700000013',
            message='Notice',
            status='sent',
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                'sms_management:delete_sent_recipient',
                args=(campaign.pk, recipient.pk),
            ),
            {'recipient_type': 'guardian'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('sms_management:dashboard')}?recipient_type=guardian")
        self.assertFalse(SMSRecipient.objects.filter(pk=recipient.pk).exists())
        campaign.refresh_from_db()
        self.assertEqual(campaign.recipient_count, 0)

    def test_authorized_sms_admin_can_delete_history_created_by_another_user(self):
        campaign_owner = get_user_model().objects.create_user(
            username='sms-campaign-owner',
            password='test-password',
        )
        campaign = SMSCampaign.objects.create(
            created_by=campaign_owner,
            audience='all_guardians',
            title='Other admin sent notice',
            content='Notice',
            recipient_count=1,
        )
        recipient = SMSRecipient.objects.create(
            campaign=campaign,
            recipient_type='guardian',
            recipient_name='Guardian',
            phone_number='+8801700000017',
            message='Notice',
            status='delivered',
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                'sms_management:delete_sent_recipient',
                args=(campaign.pk, recipient.pk),
            ),
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(SMSRecipient.objects.filter(pk=recipient.pk).exists())

    def test_submitted_sms_history_can_be_deleted_without_a_resend_action(self):
        campaign = SMSCampaign.objects.create(
            created_by=self.user,
            audience='all_guardians',
            title='Submitted notice',
            content='Notice',
            recipient_count=1,
        )
        recipient = SMSRecipient.objects.create(
            campaign=campaign,
            recipient_type='guardian',
            recipient_name='Guardian',
            phone_number='+8801700000014',
            message='Notice',
            status='submitted',
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                'sms_management:delete_sent_recipient',
                args=(campaign.pk, recipient.pk),
            ),
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(SMSRecipient.objects.filter(pk=recipient.pk).exists())

    def test_history_category_navigation_filters_recipient_rows(self):
        guardian_campaign = SMSCampaign.objects.create(
            created_by=self.user,
            audience='all_guardians',
            title='Guardian history',
            content='Guardian content',
        )
        SMSRecipient.objects.create(
            campaign=guardian_campaign,
            recipient_type='guardian',
            recipient_name='Guardian visible',
            phone_number='+8801700000015',
            message='Guardian message',
        )
        teacher_campaign = SMSCampaign.objects.create(
            created_by=self.user,
            audience='all_teachers',
            title='Teacher history',
            content='Teacher content',
        )
        SMSRecipient.objects.create(
            campaign=teacher_campaign,
            recipient_type='teacher',
            recipient_name='Teacher hidden',
            phone_number='+8801700000016',
            message='Teacher message',
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('sms_management:dashboard'),
            {'recipient_type': 'guardian'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Guardian visible')
        self.assertNotContains(response, 'Teacher hidden')

    def test_test_sms_form_shows_personalized_confirmation_preview(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('sms_management:dashboard'),
            {
                'gateway': 'sms_net_bd',
                'audience': 'test',
                'title': 'Test SMS',
                'message': 'Hello {name}',
                'test_number': '01800000000',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hello Test recipient')
        self.assertContains(response, '+8801800000000')

    def test_headmaster_can_open_sms_dashboard_from_their_dashboard(self):
        headmaster_user = get_user_model().objects.create_user(
            username='headmaster',
            password='test-password',
        )
        Teacher.objects.create(
            user=headmaster_user,
            teacher_id='HM-TEST',
            teacher_name='Test Headmaster',
            designation='Headmaster',
            mobile='01800000000',
            email='headmaster-test@example.com',
            teacher_img='teachers/test-headmaster.png',
            assigned_class='6',
        )
        self.client.force_login(headmaster_user)

        dashboard_response = self.client.get(reverse('myteacher:dashboard'))
        sms_response = self.client.get(reverse('sms_management:dashboard'))

        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, reverse('sms_management:dashboard'))
        self.assertEqual(sms_response.status_code, 200)

    def test_non_staff_user_cannot_access_dashboard_even_with_permission(self):
        non_staff = get_user_model().objects.create_user(
            username='non-staff',
            password='test-password',
        )
        permission = Permission.objects.get(codename='access_sms_dashboard')
        non_staff.user_permissions.add(permission)
        self.client.force_login(non_staff)
        self.assertEqual(self.client.get(reverse('sms_management:dashboard')).status_code, 403)

    @override_settings(HTTPSMS_API_KEY='test-key', HTTPSMS_FROM_NUMBER='+8801700000000')
    @patch('sms_management.services.requests.post')
    def test_http_sms_request_uses_documented_endpoint_and_payload(self, post):
        campaign = SMSCampaign.objects.create(
            created_by=self.user,
            audience='test',
            content='Hello {name}',
        )
        recipient = SMSRecipient.objects.create(
            campaign=campaign,
            recipient_type='test',
            recipient_name='Test recipient',
            phone_number='+8801700000009',
            message='Hello Test recipient',
        )
        response = Mock()
        response.ok = True
        response.status_code = 200
        response.json.return_value = {
            'status': 'success',
            'data': {'id': 'provider-id'},
        }
        post.return_value = response

        send_sms(recipient)

        args, kwargs = post.call_args
        self.assertEqual(args[0], HTTPSMS_SEND_URL)
        self.assertEqual(kwargs['headers']['x-api-key'], 'test-key')
        self.assertEqual(kwargs['json']['from'], '+8801700000000')
        self.assertEqual(kwargs['json']['to'], '+8801700000009')
        self.assertEqual(kwargs['json']['content'], 'Hello Test recipient')
        self.assertEqual(recipient.status, 'accepted')
        self.assertEqual(recipient.provider_message_id, 'provider-id')

    def test_webhook_delivery_updates_recipient_status(self):
        campaign = SMSCampaign.objects.create(
            created_by=self.user,
            audience='test',
            content='Test',
            status='accepted',
        )
        recipient = SMSRecipient.objects.create(
            campaign=campaign,
            recipient_type='test',
            recipient_name='Test recipient',
            phone_number='+8801700000009',
            message='Test',
            request_id='10ad7c22-242f-4fa2-b244-1cd6b60d0ad3',
            provider_message_id='provider-id',
            status='accepted',
        )

        self.assertTrue(process_webhook_event({
            'id': 'event-delivery-1',
            'type': 'message.phone.delivered',
            'data': {
                'id': 'provider-id',
                'contact': '+8801700000009',
                'owner': '+8801700000000',
                'content': 'Test',
            },
        }))
        recipient.refresh_from_db()
        campaign.refresh_from_db()
        self.assertEqual(recipient.status, 'delivered')
        self.assertEqual(campaign.status, 'delivered')

    def _create_webhook_recipient(self, provider_message_id='provider-webhook-id'):
        campaign = SMSCampaign.objects.create(
            created_by=self.user,
            audience='test',
            content='Test',
            status='accepted',
        )
        recipient = SMSRecipient.objects.create(
            campaign=campaign,
            recipient_type='test',
            recipient_name='Test recipient',
            phone_number='+8801700000009',
            message='Test',
            provider_message_id=provider_message_id,
            status='accepted',
        )
        return campaign, recipient

    def _signed_webhook_post(self, payload, event_type=None, signing_key='webhook-test-key'):
        token = _make_jwt(signing_key)
        return self.client.post(
            reverse('httpsms_webhook'),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
            HTTP_X_EVENT_TYPE=event_type or payload.get('type', ''),
        )

    @override_settings(HTTPSMS_WEBHOOK_SIGNING_KEY='webhook-test-key')
    def test_root_webhook_url_updates_all_supported_event_statuses(self):
        cases = (
            ('message.phone.sent', 'sent', {'id': 'provider-sent-id'}),
            ('message.phone.delivered', 'delivered', {'id': 'provider-delivered-id'}),
            ('message.send.failed', 'failed', {'id': 'provider-failed-id'}),
            ('message.send.expired', 'expired', {'message_id': 'provider-expired-id'}),
        )
        for index, (event_type, expected_status, message_id_field) in enumerate(cases):
            with self.subTest(event_type=event_type):
                provider_message_id = next(iter(message_id_field.values()))
                _, recipient = self._create_webhook_recipient(provider_message_id)
                payload = {
                    'id': f'cloud-event-{index}',
                    'type': event_type,
                    'data': {
                        **message_id_field,
                        'contact': '+8801700000009',
                        'owner': '+8801700000000',
                        'content': 'Test SMS',
                    },
                }

                response = self._signed_webhook_post(payload)

                self.assertEqual(response.status_code, 200)
                recipient.refresh_from_db()
                self.assertEqual(recipient.status, expected_status)

        self.assertEqual(SMSWebhookEvent.objects.count(), 4)

    @override_settings(HTTPSMS_WEBHOOK_SIGNING_KEY='webhook-test-key')
    def test_duplicate_webhook_event_is_not_processed_twice(self):
        _, recipient = self._create_webhook_recipient()
        payload = {
            'id': 'duplicate-event-id',
            'type': 'message.phone.delivered',
            'data': {
                'id': 'provider-webhook-id',
                'contact': '+8801700000009',
                'owner': '+8801700000000',
                'content': 'Test SMS',
            },
        }

        first = self._signed_webhook_post(payload)
        second = self._signed_webhook_post(payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()['result'], 'duplicate')
        self.assertEqual(SMSWebhookEvent.objects.filter(event_id='duplicate-event-id').count(), 1)
        recipient.refresh_from_db()
        self.assertEqual(recipient.status, 'delivered')

    def test_request_id_can_correlate_event_before_api_response_saves_message_id(self):
        campaign = SMSCampaign.objects.create(
            created_by=self.user,
            audience='test',
            content='Test',
            status='sending',
        )
        recipient = SMSRecipient.objects.create(
            campaign=campaign,
            recipient_type='test',
            recipient_name='Test recipient',
            phone_number='+8801700000009',
            message='Test',
            request_id='10ad7c22-242f-4fa2-b244-1cd6b60d0ad3',
            status='pending',
        )
        event = {
            'id': 'early-webhook-event',
            'type': 'message.phone.delivered',
            'data': {
                'id': 'provider-id-from-webhook',
                'request_id': '10ad7c22-242f-4fa2-b244-1cd6b60d0ad3',
                'contact': '+8801700000009',
                'owner': '+8801700000000',
                'content': 'Test SMS',
            },
        }

        self.assertEqual(process_webhook_event(event), 'processed')
        recipient.refresh_from_db()
        self.assertEqual(recipient.provider_message_id, 'provider-id-from-webhook')
        self.assertEqual(recipient.status, 'delivered')

    @override_settings(HTTPSMS_WEBHOOK_SIGNING_KEY='webhook-test-key')
    def test_invalid_signature_is_rejected(self):
        payload = {
            'id': 'invalid-signature-event',
            'type': 'message.phone.sent',
            'data': {
                'id': 'provider-id',
                'contact': '+8801700000009',
                'owner': '+8801700000000',
            },
        }
        response = self._signed_webhook_post(payload, signing_key='wrong-signing-key')

        self.assertEqual(response.status_code, 403)
        self.assertEqual(SMSWebhookEvent.objects.count(), 0)

    @override_settings(HTTPSMS_WEBHOOK_SIGNING_KEY='webhook-test-key')
    def test_invalid_json_is_rejected(self):
        response = self.client.post(
            reverse('httpsms_webhook'),
            data='{not-json',
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {_make_jwt("webhook-test-key")}',
            HTTP_X_EVENT_TYPE='message.phone.sent',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(SMSWebhookEvent.objects.count(), 0)

    @override_settings(HTTPSMS_WEBHOOK_SIGNING_KEY='webhook-test-key')
    def test_missing_required_fields_are_rejected(self):
        payload = {
            'id': 'missing-fields-event',
            'type': 'message.phone.sent',
            'data': {'contact': '+8801700000009', 'owner': '+8801700000000'},
        }
        response = self._signed_webhook_post(payload)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(SMSWebhookEvent.objects.count(), 0)

    @override_settings(HTTPSMS_WEBHOOK_SIGNING_KEY='webhook-test-key')
    def test_unknown_message_id_is_recorded_without_updating_another_recipient(self):
        _, recipient = self._create_webhook_recipient()
        payload = {
            'id': 'unknown-message-event',
            'type': 'message.phone.delivered',
            'data': {
                'id': 'not-a-known-provider-id',
                'contact': '+8801700000009',
                'owner': '+8801700000000',
                'content': 'Test SMS',
            },
        }

        response = self._signed_webhook_post(payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['result'], 'unmatched')
        self.assertEqual(
            SMSWebhookEvent.objects.get(event_id='unknown-message-event').processing_status,
            'unmatched',
        )
        recipient.refresh_from_db()
        self.assertEqual(recipient.status, 'accepted')

    @override_settings(HTTPSMS_WEBHOOK_SIGNING_KEY='webhook-test-key')
    def test_message_id_with_wrong_recipient_number_does_not_update_recipient(self):
        _, recipient = self._create_webhook_recipient()
        payload = {
            'id': 'wrong-recipient-event',
            'type': 'message.phone.delivered',
            'data': {
                'id': 'provider-webhook-id',
                'contact': '+8801700000010',
                'owner': '+8801700000000',
                'content': 'Test SMS',
            },
        }

        response = self._signed_webhook_post(payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['result'], 'unmatched')
        recipient.refresh_from_db()
        self.assertEqual(recipient.status, 'accepted')

    @override_settings(HTTPSMS_WEBHOOK_SIGNING_KEY='webhook-test-key')
    @patch('sms_management.services.SMSWebhookEvent.objects.get_or_create')
    def test_database_error_returns_retryable_server_response(self, get_or_create):
        get_or_create.side_effect = DatabaseError('database unavailable')
        payload = {
            'id': 'database-error-event',
            'type': 'message.phone.delivered',
            'data': {
                'id': 'provider-id',
                'contact': '+8801700000009',
                'owner': '+8801700000000',
                'content': 'Test SMS',
            },
        }

        response = self._signed_webhook_post(payload)

        self.assertEqual(response.status_code, 503)

    @override_settings(HTTPSMS_WEBHOOK_SIGNING_KEY='webhook-test-key')
    def test_webhook_rejects_mismatched_event_type_header(self):
        payload = {
            'id': 'mismatched-event',
            'type': 'message.phone.sent',
            'data': {
                'id': 'provider-id',
                'contact': '+8801700000009',
                'owner': '+8801700000000',
            },
        }
        response = self._signed_webhook_post(payload, event_type='message.phone.failed')

        self.assertEqual(response.status_code, 400)

    def test_webhook_accepts_only_post_requests(self):
        self.assertEqual(self.client.get(reverse('httpsms_webhook')).status_code, 405)

    @override_settings(HTTPSMS_API_KEY='test-key', HTTPSMS_FROM_NUMBER='+8801700000000')
    @patch('sms_management.services.requests.post', side_effect=Timeout)
    def test_api_timeout_is_unknown_and_is_not_reported_as_delivered(self, post):
        campaign = SMSCampaign.objects.create(
            created_by=self.user,
            audience='test',
            content='Test',
        )
        recipient = SMSRecipient.objects.create(
            campaign=campaign,
            recipient_type='test',
            recipient_name='Test recipient',
            phone_number='+8801700000009',
            message='Test',
        )

        send_sms(recipient)

        recipient.refresh_from_db()
        self.assertEqual(recipient.status, 'unknown')
        self.assertIn('Do not retry automatically', recipient.error_message)
        post.assert_called_once()

    @override_settings(HTTPSMS_API_KEY='test-key', HTTPSMS_FROM_NUMBER='+8801700000000')
    def test_bulk_campaign_cannot_send_before_delivered_test(self):
        campaign = SMSCampaign.objects.create(
            created_by=self.user,
            audience='all_guardians',
            content='School notice',
            status='draft',
        )
        SMSRecipient.objects.create(
            campaign=campaign,
            recipient_type='guardian',
            recipient_name='Kamal Ahmed',
            phone_number='+8801700000001',
            message='School notice',
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('sms_management:confirm_send', args=(campaign.pk,)),
            {'confirmation_token': str(campaign.confirmation_token)},
        )

        campaign.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(campaign.status, 'draft')

    def test_confirm_rejects_malformed_confirmation_token(self):
        campaign = SMSCampaign.objects.create(
            created_by=self.user,
            audience='test',
            content='Test',
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('sms_management:confirm_send', args=(campaign.pk,)),
            {'confirmation_token': 'not-a-uuid'},
        )

        self.assertEqual(response.status_code, 302)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, 'draft')

    @override_settings(HTTPSMS_WEBHOOK_SIGNING_KEY='test-signing-key')
    def test_webhook_rejects_missing_signature(self):
        response = self.client.post(
            reverse('sms_management:webhook'),
            data=json.dumps({'type': 'message.phone.delivered', 'data': {}}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_webhook_token_verifies_hs256_signature(self):
        signing_key = 'test-signing-key'
        header = _encode_json({'alg': 'HS256', 'typ': 'JWT'})
        payload = _encode_json({'exp': int(time.time()) + 60})
        signing_input = f'{header}.{payload}'
        signature = hmac.new(
            signing_key.encode(),
            signing_input.encode(),
            hashlib.sha256,
        ).digest()
        token = f'{signing_input}.{_encode_bytes(signature)}'

        self.assertTrue(verify_webhook_token(f'Bearer {token}', signing_key))
        self.assertFalse(verify_webhook_token(f'Bearer {token}', 'wrong-key'))


def _encode_bytes(value):
    return base64.urlsafe_b64encode(value).decode().rstrip('=')


def _encode_json(value):
    return _encode_bytes(json.dumps(value, separators=(',', ':')).encode())


def _make_jwt(signing_key):
    header = _encode_json({'alg': 'HS256', 'typ': 'JWT'})
    payload = _encode_json({'exp': int(time.time()) + 60})
    signing_input = f'{header}.{payload}'
    signature = hmac.new(
        signing_key.encode(),
        signing_input.encode(),
        hashlib.sha256,
    ).digest()
    return f'{signing_input}.{_encode_bytes(signature)}'


@override_settings(
    SMS_GATEWAY_API_KEY='sms-gateway-test-key',
    SMS_GATEWAY_SENDER_ID='',
    SMS_GATEWAY_CONTENT_ID='approved-content-id',
)
class SMSNetProviderTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='sms-net-admin',
            password='test-password',
            is_staff=True,
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename='access_sms_dashboard')
        )
        self.campaign = SMSCampaign.objects.create(
            created_by=self.user,
            audience='test',
            title='Administrator test',
            content='Test message',
            recipient_count=1,
        )
        self.recipient = SMSRecipient.objects.create(
            campaign=self.campaign,
            recipient_type='test',
            recipient_name='Test recipient',
            phone_number='+8801700000009',
            message='Test message',
        )

    @patch('sms_management.provider.requests.post')
    def test_submit_uses_form_data_and_records_provider_request_id(self, post):
        response = Mock(status_code=200, ok=True)
        response.json.return_value = {
            'error': 0,
            'msg': 'Request successfully submitted.',
            'data': {'request_id': 'request-123'},
        }
        post.return_value = response

        submit_recipient(self.recipient, self.campaign)

        args, kwargs = post.call_args
        self.assertEqual(args[0], SEND_URL)
        self.assertNotIn('sms-gateway-test-key', args[0])
        self.assertEqual(kwargs['data']['api_key'], 'sms-gateway-test-key')
        self.assertEqual(kwargs['data']['msg'], 'Test message')
        self.assertEqual(kwargs['data']['to'], '8801700000009')
        self.assertEqual(self.recipient.__class__.objects.get(pk=self.recipient.pk).status, 'submitted')
        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.api_request_id, 'request-123')
        self.assertEqual(self.recipient.api_error_code, 0)
        self.assertIsNotNone(self.recipient.submitted_at)

    @patch('sms_management.provider.requests.post')
    def test_scheduled_submission_uses_provider_schedule_and_content_id(self, post):
        self.campaign.scheduled_at = timezone.now() + timedelta(days=1)
        self.campaign.save(update_fields=('scheduled_at',))
        response = Mock(status_code=200, ok=True)
        response.json.return_value = {'error': 0, 'data': {'request_id': 'scheduled-123'}}
        post.return_value = response

        submit_recipient(self.recipient, self.campaign)

        sent_data = post.call_args.kwargs['data']
        self.assertEqual(
            sent_data['schedule'],
            timezone.localtime(self.campaign.scheduled_at).strftime('%Y-%m-%d %H:%M:%S'),
        )
        self.assertEqual(sent_data['content_id'], 'approved-content-id')

    def _set_recent_balance(self):
        session = self.client.session
        session['sms_gateway_balance'] = {
            'amount': '25.50',
            'checked_at': timezone.localtime().isoformat(timespec='minutes'),
        }
        session.save()

    @patch('sms_management.provider.requests.post')
    def test_confirmed_test_campaign_submits_only_after_balance_and_explicit_confirmation(self, post):
        self.client.force_login(self.user)
        self._set_recent_balance()
        response = Mock(status_code=200, ok=True)
        response.json.return_value = {
            'error': 0,
            'data': {'request_id': 'request-confirmed-test'},
        }
        post.return_value = response

        result = self.client.post(
            reverse('sms_management:confirm_send', args=(self.campaign.pk,)),
            {
                'confirmation_token': str(self.campaign.confirmation_token),
                'confirm_send': 'yes',
            },
        )

        self.assertEqual(result.status_code, 302)
        self.recipient.refresh_from_db()
        self.campaign.refresh_from_db()
        self.assertEqual(self.recipient.status, 'submitted')
        self.assertEqual(self.campaign.status, 'submitted')
        post.assert_called_once()

    @patch('sms_management.provider.requests.post')
    def test_confirmation_without_explicit_checkbox_never_calls_provider(self, post):
        self.client.force_login(self.user)
        self._set_recent_balance()

        self.client.post(
            reverse('sms_management:confirm_send', args=(self.campaign.pk,)),
            {'confirmation_token': str(self.campaign.confirmation_token)},
        )

        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, 'draft')
        post.assert_not_called()

    @override_settings(SMS_GATEWAY_CONTENT_ID='')
    @patch('sms_management.provider.requests.post')
    def test_bulk_campaign_without_content_id_is_blocked(self, post):
        test_campaign = SMSCampaign.objects.create(
            created_by=self.user,
            audience='test',
            title='Prior test',
            content='Test',
            status='sent',
        )
        SMSRecipient.objects.create(
            campaign=test_campaign,
            recipient_type='test',
            recipient_name='Test recipient',
            phone_number='+8801700000010',
            message='Test',
            status='sent',
        )
        campaign = SMSCampaign.objects.create(
            created_by=self.user,
            audience='all_guardians',
            title='Bulk campaign',
            content='Notice',
            recipient_count=2,
        )
        for last_digit in ('1', '2'):
            SMSRecipient.objects.create(
                campaign=campaign,
                recipient_type='guardian',
                recipient_name='Guardian',
                phone_number=f'+880170000000{last_digit}',
                message='Notice',
            )
        self.client.force_login(self.user)
        self._set_recent_balance()

        self.client.post(
            reverse('sms_management:confirm_send', args=(campaign.pk,)),
            {
                'confirmation_token': str(campaign.confirmation_token),
                'confirm_send': 'yes',
            },
        )

        campaign.refresh_from_db()
        self.assertEqual(campaign.status, 'draft')
        post.assert_not_called()

    @patch('sms_management.provider.requests.post')
    def test_provider_error_421_explains_registered_number_restriction(self, post):
        response = Mock(status_code=200, ok=True)
        response.json.return_value = {'error': 421, 'msg': 'Recharge required.'}
        post.return_value = response

        submit_recipient(self.recipient, self.campaign)

        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.status, 'failed')
        self.assertEqual(self.recipient.api_error_code, 421)
        self.assertIn('registered with SMS.NET.BD', self.recipient.error_message)

    @patch('sms_management.provider.requests.post')
    def test_uncertain_submission_is_not_retried(self, post):
        post.side_effect = Timeout

        submit_recipient(self.recipient, self.campaign)
        submit_recipient(self.recipient, self.campaign)

        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.status, 'unknown')
        self.assertIn('do not retry automatically', self.recipient.error_message)
        post.assert_called_once()

    @patch('sms_management.provider.requests.post')
    def test_balance_posts_api_key_as_form_data_not_in_url(self, get):
        response = Mock(status_code=200, ok=True)
        response.json.return_value = {'error': 0, 'data': {'balance': '25.50'}}
        get.return_value = response

        balance = check_balance()

        args, kwargs = get.call_args
        self.assertEqual(args[0], BALANCE_URL)
        self.assertNotIn('sms-gateway-test-key', args[0])
        self.assertEqual(kwargs['data'], {'api_key': 'sms-gateway-test-key'})
        self.assertEqual(balance['amount'], '25.50')

    @patch('sms_management.provider.requests.post')
    def test_report_posts_api_key_as_form_data_not_in_url(self, get):
        self.recipient.api_request_id = 'request-123'
        self.recipient.status = 'submitted'
        self.recipient.save()
        response = Mock(status_code=200, ok=True)
        response.json.return_value = {
            'error': 0,
            'data': {'status': 'sent', 'charge': '2.50'},
        }
        get.return_value = response

        result = refresh_recipient_report(self.recipient)

        self.recipient.refresh_from_db()
        self.assertEqual(result, 'Provider report status: sent.')
        self.assertEqual(self.recipient.status, 'sent')
        self.assertEqual(str(self.recipient.sms_charge), '2.5000')
        self.assertEqual(get.call_args.args[0], f'{REPORT_URL}request-123/')
        self.assertEqual(get.call_args.kwargs['data'], {'api_key': 'sms-gateway-test-key'})

    @patch('sms_management.provider.requests.post')
    def test_successful_report_without_delivery_status_does_not_claim_sent(self, get):
        self.recipient.api_request_id = 'request-123'
        self.recipient.status = 'submitted'
        self.recipient.save()
        response = Mock(status_code=200, ok=True)
        response.json.return_value = {'error': 0, 'msg': 'Request found.'}
        get.return_value = response

        refresh_recipient_report(self.recipient)

        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.status, 'submitted')

    def test_provider_error_message_covers_documented_codes(self):
        self.assertEqual(set(API_ERROR_MESSAGES), {
            0, 400, 403, 404, 405, 409, 410, 411, 412, 413, 414, 415, 416, 417, 420, 421,
        })
        self.assertIn('first balance recharge', error_message(421))

    @override_settings(
        HTTPSMS_API_KEY='httpsms-test-key',
        HTTPSMS_PHONE_NUMBER='+8801700000000',
    )
    @patch('sms_management.provider.requests.post')
    def test_httpsms_send_uses_android_phone_and_api_key_header(self, post):
        response = Mock(status_code=200, ok=True)
        post.return_value = response

        result = send_sms_via_httpsms(
            '+8801700000009',
            'Test from phone SIM',
            request_id='request-httpsms-1',
        )

        self.assertIs(result, response)
        args, kwargs = post.call_args
        self.assertEqual(args[0], 'https://api.httpsms.com/v1/messages/send')
        self.assertEqual(kwargs['headers']['x-api-key'], 'httpsms-test-key')
        self.assertEqual(kwargs['json'], {
            'from': '+8801700000000',
            'to': '+8801700000009',
            'content': 'Test from phone SIM',
            'request_id': 'request-httpsms-1',
        })

    @override_settings(
        HTTPSMS_API_KEY='httpsms-test-key',
        HTTPSMS_PHONE_NUMBER='+8801700000000',
    )
    @patch('sms_management.provider.requests.post')
    def test_httpsms_campaign_marks_provider_acceptance_without_claiming_delivery(self, post):
        self.campaign.gateway = 'httpsms'
        self.campaign.save(update_fields=('gateway',))
        response = Mock(status_code=200, ok=True)
        response.json.return_value = {
            'status': 'success',
            'data': {'id': 'httpsms-message-1'},
        }
        post.return_value = response

        submit_httpsms_recipient(self.recipient)

        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.status, 'accepted')
        self.assertEqual(self.recipient.provider_message_id, 'httpsms-message-1')
        self.assertNotEqual(self.recipient.status, 'delivered')

    @override_settings(
        HTTPSMS_API_KEY='httpsms-test-key',
        HTTPSMS_PHONE_NUMBER='+8801700000000',
    )
    @patch('sms_management.provider.requests.post')
    def test_httpsms_timeout_is_unknown_and_will_not_be_retried(self, post):
        post.side_effect = Timeout

        submit_httpsms_recipient(self.recipient)
        submit_httpsms_recipient(self.recipient)

        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.status, 'unknown')
        self.assertIn('do not retry automatically', self.recipient.error_message)
        post.assert_called_once()

    @override_settings(
        HTTPSMS_API_KEY='httpsms-test-key',
        HTTPSMS_PHONE_NUMBER='+8801700000000',
    )
    def test_httpsms_gateway_campaign_confirm_sends_without_smsnet_balance_or_content_id(self):
        self.campaign.gateway = 'httpsms'
        self.campaign.save(update_fields=('gateway',))
        self.client.force_login(self.user)
        response = Mock(status_code=200, ok=True)
        response.json.return_value = {
            'status': 'success',
            'data': {'id': 'httpsms-confirmed-message'},
        }
        with patch('sms_management.provider.requests.post', return_value=response) as post:
            result = self.client.post(
                reverse('sms_management:confirm_send', args=(self.campaign.pk,)),
                {
                    'confirmation_token': str(self.campaign.confirmation_token),
                    'confirm_send': 'yes',
                },
            )

        self.assertEqual(result.status_code, 302)
        self.recipient.refresh_from_db()
        self.campaign.refresh_from_db()
        self.assertEqual(self.recipient.status, 'accepted')
        self.assertEqual(self.campaign.status, 'accepted')
        post.assert_called_once()

    @patch('sms_management.provider.requests.post')
    def test_balance_error_is_reported(self, get):
        response = Mock(status_code=200, ok=True)
        response.json.return_value = {'error': 417, 'msg': 'Low balance.'}
        get.return_value = response

        with self.assertRaises(SMSGatewayError) as error:
            check_balance()

        self.assertEqual(error.exception.error_code, 417)
        self.assertIn('insufficient balance', str(error.exception))

    @patch('sms_management.provider.requests.post')
    def test_provider_report_recipient_array_updates_matching_number(self, post):
        self.recipient.api_request_id = 'request-123'
        self.recipient.status = 'submitted'
        self.recipient.save()
        response = Mock(status_code=200, ok=True)
        response.json.return_value = {
            'error': 0,
            'msg': 'Success',
            'data': {
                'request_id': 123,
                'request_status': 'Complete',
                'request_charge': '0.0000',
                'recipients': [
                    {'number': '8801700000009', 'charge': '0.0000', 'status': 'Sent'},
                ],
            },
        }
        post.return_value = response

        result = refresh_recipient_report(self.recipient)

        self.recipient.refresh_from_db()
        self.assertEqual(result, 'Provider report status: sent.')
        self.assertEqual(self.recipient.status, 'sent')
        self.assertEqual(str(self.recipient.sms_charge), '0.0000')
