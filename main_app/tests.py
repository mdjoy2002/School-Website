import os
import re
import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.shortcuts import render
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from core.compression import compress_image_field
from main_app.admin import LeadershipProfileForm
from main_app.models import (
    AdmissionApplication,
    AdmissionApplySettings,
    AdmissionSequence,
    CommitteeMember,
    DailyVisitor,
    EntryPopupImage,
    GalleryCategory,
    GalleryImage,
    LeadershipProfile,
    Notice,
    VisitorProfile,
)


def home(request):
    return render(request, 'index.html')


class VisitorTrackingTests(TestCase):
    def test_counts_unique_visitors_and_new_visitors(self):
        first_response = self.client.get(reverse('home'))

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(first_response.context['visitor_counts'], {
            'today': 1,
            'total': 1,
            'new': 1,
        })
        self.assertEqual(VisitorProfile.objects.count(), 1)
        self.assertEqual(DailyVisitor.objects.count(), 1)

        repeated_response = self.client.get(reverse('home'))

        self.assertEqual(repeated_response.context['visitor_counts'], {
            'today': 1,
            'total': 1,
            'new': 1,
        })
        self.assertEqual(DailyVisitor.objects.count(), 1)

        returning_browser = Client()
        returning_browser.cookies['visitor_uuid'] = self.client.cookies['visitor_uuid'].value
        returning_response = returning_browser.get(reverse('home'))

        self.assertEqual(returning_response.context['visitor_counts'], {
            'today': 1,
            'total': 1,
            'new': 1,
        })

        second_client = Client()
        second_response = second_client.get(reverse('home'))

        self.assertEqual(second_response.context['visitor_counts'], {
            'today': 2,
            'total': 2,
            'new': 2,
        })

    def test_replaces_invalid_visitor_cookie(self):
        self.client.cookies['visitor_uuid'] = 'not-a-uuid'

        response = self.client.get(reverse('home'))

        replacement_uuid = response.cookies['visitor_uuid'].value
        self.assertNotEqual(replacement_uuid, 'not-a-uuid')
        self.assertEqual(VisitorProfile.objects.get().visitor_uuid, replacement_uuid)

    def test_admin_requests_are_not_counted(self):
        response = self.client.get('/knu2026/')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(VisitorProfile.objects.count(), 0)


class CompressionTests(SimpleTestCase):
    def test_compress_image_field_does_not_fail_on_uploaded_image(self):
        image = Image.new('RGB', (20, 20), color='red')
        buffer = BytesIO()
        image.save(buffer, format='JPEG')

        uploaded_file = SimpleUploadedFile(
            'test.jpg',
            buffer.getvalue(),
            content_type='image/jpeg'
        )

        compress_image_field(uploaded_file)

        self.assertTrue(uploaded_file.name)


class AdmissionApplicationTests(TestCase):
    def test_admission_application_is_closed_by_default(self):
        response = self.client.get(reverse('admission_application_form'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'বর্তমানে অনলাইন ভর্তি আবেদন গ্রহণ বন্ধ আছে')
        self.assertNotContains(response, 'ফরম জমা দিন')

    def test_admin_can_configure_and_activate_admission(self):
        user = get_user_model().objects.create_superuser(
            'settings_admin',
            'settings@example.com',
            'secret123',
        )
        self.client.force_login(user)
        settings_url = reverse('admin:main_app_admissionapplysettings_add')
        response = self.client.post(
            settings_url,
            {
                'is_active': 'on',
                'fee_class_6': '250.00',
                'fee_class_7': '200.00',
                'fee_class_8': '200.00',
                'fee_class_9': '300.00',
                'fee_class_10': '300.00',
                'documents_class_6': 'জন্মনিবন্ধন সনদ\nমার্কশিট',
                'documents_class_7': 'জন্মনিবন্ধন সনদ\nবার্ষিক পরীক্ষার ফলাফল',
                'bkash_enabled': 'on',
                'bkash_number': '01700000000',
                'nagad_enabled': 'on',
                'nagad_number': '01800000000',
                'in_school_enabled': 'on',
                'payment_instructions': 'পেমেন্টের পর রেফারেন্স দিন',
                'ticker_text': '২০২৭ শিক্ষাবর্ষে ভর্তি চলছে',
            },
        )

        self.assertEqual(response.status_code, 302)
        settings = AdmissionApplySettings.objects.get()
        self.assertTrue(settings.is_active)
        self.assertEqual(settings.fee_class_6, 250)
        self.assertEqual(settings.documents_for_class('ষষ্ঠ'), ['জন্মনিবন্ধন সনদ', 'মার্কশিট'])
        self.assertEqual(settings.documents_for_class('সপ্তম'), ['জন্মনিবন্ধন সনদ', 'বার্ষিক পরীক্ষার ফলাফল'])
        self.assertEqual(settings.bkash_number, '01700000000')
        self.assertEqual(settings.nagad_number, '01800000000')
        form_response = self.client.get(reverse('admission_application_form'))
        self.assertContains(form_response, 'id="admissionClass"')
        self.assertContains(form_response, '250.00')
        self.assertEqual(
            self.client.get(reverse('admin:main_app_admissionapplysettings_changelist')).status_code,
            200,
        )

        response = self.client.post(
            reverse('admin:main_app_admissionapplysettings_change', args=[settings.pk]),
            {
                'fee_class_6': '250.00',
                'fee_class_7': '200.00',
                'fee_class_8': '200.00',
                'fee_class_9': '300.00',
                'fee_class_10': '300.00',
                'documents_class_6': 'জন্মনিবন্ধন সনদ\nমার্কশিট',
                'documents_class_7': 'জন্মনিবন্ধন সনদ\nবার্ষিক পরীক্ষার ফলাফল',
                'bkash_enabled': 'on',
                'bkash_number': '01700000000',
                'nagad_enabled': 'on',
                'nagad_number': '01800000000',
                'in_school_enabled': 'on',
                'payment_instructions': 'পেমেন্টের পর রেফারেন্স দিন',
                'ticker_text': '২০২৭ শিক্ষাবর্ষে ভর্তি চলছে',
            },
        )
        self.assertEqual(response.status_code, 302)
        settings.refresh_from_db()
        self.assertFalse(settings.is_active)

    def test_student_form_shows_configured_documents_for_selected_class(self):
        AdmissionApplySettings.objects.create(
            is_active=True,
            documents_class_6='জন্মনিবন্ধন সনদ\nমার্কশিট',
            documents_class_7='জন্মনিবন্ধন সনদ\nবার্ষিক পরীক্ষার ফলাফল',
        )

        response = self.client.get(reverse('admission_application_form'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class-documents-data')
        self.assertContains(response, "checkbox.name = 'submitted_documents'")
        self.assertContains(response, 'খন্দকার নাসের উদ্দীন মাধ্যমিক বিদ্যালয়')
        self.assertContains(response, 'Khondoker Naser Uddin High School')
        self.assertContains(response, 'হাজী ফয়েজ উদ্দীন ক্রস রোড')
        self.assertContains(response, 'বিদ্যালয় কোডঃ ৩৫৭৪')
        self.assertContains(response, 'EIIN: 117407')
        self.assertContains(response, 'প্রধান শিক্ষকের স্বাক্ষর')
        self.assertContains(response, 'শিক্ষাই জাতির মেরুদন্ড')
        self.assertNotContains(response, '৮. অন্যান্য তথ্য')
        self.assertEqual(
            response.context['document_options'],
            {
                'ষষ্ঠ': ['জন্মনিবন্ধন সনদ', 'মার্কশিট'],
                'সপ্তম': ['জন্মনিবন্ধন সনদ', 'বার্ষিক পরীক্ষার ফলাফল'],
                'অষ্টম': [],
                'নবম': [],
                'দশম': [],
            },
        )

    def test_active_admission_is_shown_in_navigation_and_news_ticker(self):
        AdmissionApplySettings.objects.create(
            is_active=True,
            ticker_text='২০২৭ শিক্ষাবর্ষে ভর্তি চলছে',
        )

        response = self.client.get(reverse('home'))

        self.assertContains(response, '২০২৭ শিক্ষাবর্ষে ভর্তি চলছে')
        self.assertContains(response, 'এডমিশন আবেদন')
        self.assertContains(response, reverse('admission_application_form'))
        self.assertContains(response, reverse('admission_status_lookup'))
        application_form = self.client.get(reverse('admission_application_form'))
        self.assertContains(application_form, reverse('home'))
        self.assertContains(application_form, 'হোম পেজে ফিরে যান')

        AdmissionApplySettings.objects.update(is_active=False)
        inactive_response = self.client.get(reverse('home'))
        self.assertNotContains(inactive_response, '২০২৭ শিক্ষাবর্ষে ভর্তি চলছে')
        self.assertNotContains(inactive_response, 'এডমিশন আবেদন')

    def test_online_payment_requires_reference_and_disabled_methods_are_rejected(self):
        AdmissionApplySettings.objects.create(
            is_active=True,
            fee_class_6='250.00',
            bkash_enabled=True,
            nagad_enabled=False,
            in_school_enabled=True,
        )
        application_data = {
            'student_name_bn': 'পরীক্ষার্থী',
            'student_name_en': 'Test Student',
            'date_of_birth': '2012-01-02',
            'birth_reg_no': '1234567890',
            'gender': 'ছেলে',
            'nationality': 'বাংলাদেশি',
            'email': 'applicant@example.com',
            'admission_class': 'ষষ্ঠ',
            'academic_year': '2027',
            'guardian_mobile': '০১৭১৪৯৩৯১২২',
        }

        response = self.client.post(
            reverse('admission_application_form'),
            {**application_data, 'payment_method': 'bkash'},
        )
        self.assertContains(response, 'Transaction ID / রেফারেন্স নম্বর দিন')
        self.assertFalse(AdmissionApplication.objects.exists())

        response = self.client.post(
            reverse('admission_application_form'),
            {
                **application_data,
                'payment_method': 'nagad',
                'payment_reference': 'TEST-123',
            },
        )
        self.assertContains(response, 'চালু থাকা একটি বৈধ পেমেন্ট মাধ্যম')
        self.assertFalse(AdmissionApplication.objects.exists())

    def test_student_photo_over_300_kb_is_rejected(self):
        AdmissionApplySettings.objects.create(is_active=True, in_school_enabled=True)
        response = self.client.post(
            reverse('admission_application_form'),
            data={
                'student_name_bn': 'পরীক্ষার্থী',
                'student_name_en': 'Test Student',
                'date_of_birth': '2012-01-02',
                'birth_reg_no': '1234567890',
                'gender': 'ছেলে',
                'nationality': 'বাংলাদেশি',
                'father_name_bn': 'আব্দুল করিম',
                'father_name_en': 'Abdul Karim',
                'mother_name_bn': 'রহিমা খাতুন',
                'mother_name_en': 'Rahima Khatun',
                'email': 'applicant@example.com',
                'admission_class': 'ষষ্ঠ',
                'academic_year': '2027',
                'payment_method': 'in_school',
                'student_photo': SimpleUploadedFile(
                    'student.jpg',
                    b'x' * (300 * 1024 + 1),
                    content_type='image/jpeg',
                ),
            },
        )

        self.assertContains(response, 'ছবির আকার ৩০০ KB-এর মধ্যে হতে হবে')
        self.assertFalse(AdmissionApplication.objects.exists())

    def test_applications_get_sequential_class_and_year_rolls(self):
        AdmissionApplySettings.objects.create(is_active=True, in_school_enabled=True)
        with tempfile.TemporaryDirectory() as media_root, override_settings(
            MEDIA_ROOT=media_root,
            EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        ):
            for index in range(2):
                image_buffer = BytesIO()
                Image.new('RGB', (24, 32), color='white').save(image_buffer, format='JPEG')
                response = self.client.post(
                    reverse('admission_application_form'),
                    data={
                        'student_name_bn': f'পরীক্ষার্থী {index}',
                        'student_name_en': f'Test Student {index}',
                        'date_of_birth': '2012-01-02',
                        'birth_reg_no': f'123456789{index}',
                        'gender': 'ছেলে',
                        'nationality': 'বাংলাদেশি',
                        'father_name_bn': 'আব্দুল করিম',
                        'father_name_en': 'Abdul Karim',
                        'mother_name_bn': 'রহিমা খাতুন',
                        'mother_name_en': 'Rahima Khatun',
                        'email': f'applicant{index}@example.com',
                        'guardian_mobile': '01714939122',
                        'admission_class': 'ষষ্ঠ',
                        'academic_year': '2027',
                        'payment_method': 'in_school',
                        'student_photo': SimpleUploadedFile(
                            f'student-{index}.jpg',
                            image_buffer.getvalue(),
                            content_type='image/jpeg',
                        ),
                    },
                )
                self.assertRedirects(response, reverse('admission_application_print'))

            applications = list(
                AdmissionApplication.objects.order_by('class_roll_number')
            )
            self.assertEqual(
                [application.application_id for application in applications],
                [
                    'KNU-01714939122-2027-06-0001',
                    'KNU-01714939122-2027-06-0002',
                ],
            )
            self.assertEqual(
                [application.class_roll_number for application in applications],
                [1, 2],
            )
            sequence = AdmissionSequence.objects.get(admission_class='ষষ্ঠ', academic_year=2027)
            self.assertEqual(sequence.next_application_number, 3)
            self.assertEqual(sequence.next_roll_number, 3)

    def test_submission_is_saved_as_pdf_and_visible_in_admin(self):
        AdmissionApplySettings.objects.create(
            is_active=True,
            fee_class_6='250.00',
            documents_class_6='জন্মনিবন্ধন সনদ\nমার্কশিট\nছাড়পত্র (TC)',
            bkash_enabled=True,
            nagad_enabled=False,
            in_school_enabled=True,
        )
        user = get_user_model().objects.create_superuser(
            'admission_admin',
            'admission@example.com',
            'secret123',
        )
        image_buffer = BytesIO()
        Image.new('RGB', (48, 64), color='white').save(image_buffer, format='JPEG')
        uploaded_photo = SimpleUploadedFile(
            'student.jpg',
            image_buffer.getvalue(),
            content_type='image/jpeg',
        )

        with tempfile.TemporaryDirectory() as media_root, override_settings(
            MEDIA_ROOT=media_root,
            EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        ):
            response = self.client.post(
                reverse('admission_application_form'),
                data={
                    'student_name_bn': 'পরীক্ষার্থী',
                    'student_name_en': 'Test Student',
                    'date_of_birth': '2012-01-02',
                    'birth_reg_no': '1234567890',
                    'gender': 'ছেলে',
                    'nationality': 'বাংলাদেশি',
                    'father_name_bn': 'আব্দুল করিম',
                    'father_name_en': 'Abdul Karim',
                    'mother_name_bn': 'রহিমা খাতুন',
                    'mother_name_en': 'Rahima Khatun',
                    'guardian_mobile': '০১৭১৪৯৩৯১২২',
                    'email': 'applicant@example.com',
                    'admission_class': 'ষষ্ঠ',
                    'academic_year': '2027',
                    'submitted_documents': ['জন্মনিবন্ধন সনদ', 'মার্কশিট', 'অন্য একটি অগ্রহণযোগ্য কাগজ'],
                    'payment_method': 'bkash',
                    'payment_reference': 'TXN-123456',
                    'admission_id': 'UNTRUSTED',
                    'student_photo': uploaded_photo,
                },
            )
            self.assertRedirects(response, reverse('admission_application_print'))

            application = AdmissionApplication.objects.get()
            self.addCleanup(application.student_photo.delete, save=False)
            self.addCleanup(application.pdf_file.delete, save=False)
            self.assertEqual(application.application_data['student_name_bn'], 'পরীক্ষার্থী')
            self.assertEqual(application.application_data['attached_documents'], ['জন্মনিবন্ধন সনদ', 'মার্কশিট'])
            self.assertEqual(application.application_data['payment_method'], 'bkash')
            self.assertEqual(application.application_data['application_fee'], '250.00')
            self.assertEqual(application.application_fee, 250)
            self.assertEqual(application.application_id, 'KNU-01714939122-2027-06-0001')
            self.assertEqual(application.class_roll_number, 1)
            self.assertEqual(application.assigned_roll, 1)
            self.assertEqual(len(mail.outbox), 1)
            self.assertEqual(mail.outbox[0].to, ['applicant@example.com'])
            self.assertEqual(mail.outbox[0].from_email, 'imtiazsarderjoy@gmail.com')
            self.assertIn(application.application_id, mail.outbox[0].body)
            self.assertEqual(application.application_data['payment_reference'], 'TXN-123456')
            self.assertEqual(application.application_data['father_name_bn'], 'আব্দুল করিম')
            self.assertEqual(application.application_data['father_name_en'], 'Abdul Karim')
            self.assertEqual(application.application_data['mother_name_bn'], 'রহিমা খাতুন')
            self.assertEqual(application.application_data['mother_name_en'], 'Rahima Khatun')
            self.assertNotIn('admission_id', application.application_data)
            with application.pdf_file.open('rb') as pdf:
                pdf_content = pdf.read()
            self.assertTrue(pdf_content.startswith(b'%PDF-'))
            self.assertIn(b'Kalpurush', pdf_content)
            media_boxes = re.findall(rb'/MediaBox\s*\[([^\]]+)\]', pdf_content)
            self.assertTrue(media_boxes)
            for media_box in media_boxes:
                self.assertRegex(
                    media_box.decode('ascii'),
                    r'\s*0\s+0\s+595\.2756\s+841\.8898\s*',
                )
            print_view = self.client.get(reverse('admission_application_print'))
            self.assertContains(print_view, reverse('admission_application_download_pdf'))
            self.assertContains(print_view, reverse('admission_application_student_photo'))
            self.assertContains(print_view, 'পিতার পূর্ণ নাম (বাংলা)')
            self.assertContains(print_view, 'Abdul Karim')
            self.assertContains(print_view, 'রহিমা খাতুন')
            self.assertContains(print_view, application.application_id)
            self.assertContains(print_view, 'জন্মনিবন্ধন সনদ')
            self.assertContains(print_view, 'Khondoker Naser Uddin High School')
            self.assertContains(print_view, 'হাজী ফয়েজ উদ্দীন ক্রস রোড')
            self.assertContains(print_view, 'পোস্টঃ জিপিও-৯০০০, থানাঃ সোনাডাঙ্গা, জেলাঃ খুলনা')
            self.assertContains(print_view, 'মোবাঃ ০১৩০৯১১৭৪০৭, ০১৭১৪৯৩৯১২২')
            self.assertContains(print_view, 'বিদ্যালয় কোডঃ ৩৫৭৪')
            self.assertContains(print_view, 'EIIN: 117407')
            self.assertContains(print_view, 'প্রধান শিক্ষকের স্বাক্ষর')
            self.assertContains(print_view, 'শিক্ষাই জাতির মেরুদন্ড')
            self.assertNotContains(print_view, '৮. অন্যান্য তথ্য')
            public_pdf = self.client.get(reverse('admission_application_download_pdf'))
            self.assertEqual(public_pdf.status_code, 200)
            self.assertIn('test-student-class-6-2027.pdf', public_pdf['Content-Disposition'])
            public_pdf.close()
            self.assertEqual(Client().get(reverse('admission_application_download_pdf')).status_code, 404)

            self.client.force_login(user)
            listing = self.client.get(reverse('admin:main_app_admissionapplication_changelist'))
            detail = self.client.get(
                reverse('admin:main_app_admissionapplication_change', args=[application.pk])
            )
            photo = self.client.get(
                reverse('admin:main_app_admissionapplication_student_photo', args=[application.pk])
            )
            photo_content = b''.join(photo.streaming_content)
            photo.close()

            self.assertEqual(listing.status_code, 200)
            self.assertContains(listing, 'পরীক্ষার্থী')
            self.assertEqual(detail.status_code, 200)
            self.assertContains(detail, 'জন্মনিবন্ধন সনদ')
            self.assertContains(detail, 'name="payment_status"')
            self.assertContains(detail, 'name="approver_name"')
            original_pdf_name = application.pdf_file.name
            updated = self.client.post(
                reverse('admin:main_app_admissionapplication_change', args=[application.pk]),
                {
                    'status': 'APPROVED',
                    'payment_status': 'PAID',
                    'assigned_class': 'ষষ্ঠ',
                    'assigned_section': 'ক',
                    'approver_name': 'প্রধান শিক্ষক',
                    'admission_confirmed_at': '2027-01-15',
                    'office_comment': 'ভর্তি অনুমোদিত',
                },
                follow=True,
            )
            self.assertEqual(updated.status_code, 200)
            application.refresh_from_db()
            self.assertEqual(application.status, 'APPROVED')
            self.assertEqual(application.payment_status, 'PAID')
            self.assertIn('ভর্তি অনুমোদিত', application.application_data['office_comment'])
            self.assertTrue(application.pdf_file.name.rsplit('/', 1)[-1].startswith('admission-application-v9-'))
            self.assertNotEqual(application.pdf_file.name, original_pdf_name)
            download = self.client.get(
                reverse('admin:main_app_admissionapplication_download_pdf', args=[application.pk])
            )
            downloaded_pdf = b''.join(download.streaming_content)
            download.close()
            self.assertEqual(download.status_code, 200)
            self.assertEqual(download['Content-Type'], 'application/pdf')
            self.assertIn('test-student-class-6-2027.pdf', download['Content-Disposition'])
            self.assertTrue(downloaded_pdf.startswith(b'%PDF-'))
            self.assertEqual(photo['Content-Type'], 'image/jpeg')
            self.assertTrue(photo_content)

            application.pdf_file.delete(save=True)
            application.pdf_file.save(
                'admission-application-old-layout.pdf',
                SimpleUploadedFile(
                    'admission-application-old-layout.pdf',
                    b'%PDF-obsolete',
                    content_type='application/pdf',
                ),
                save=True,
            )
            upgraded = self.client.get(
                reverse('admin:main_app_admissionapplication_download_pdf', args=[application.pk])
            )
            upgraded_pdf = b''.join(upgraded.streaming_content)
            upgraded.close()
            application.refresh_from_db()
            self.assertTrue(upgraded_pdf.startswith(b'%PDF-'))
            self.assertTrue(application.pdf_file.name.rsplit('/', 1)[-1].startswith('admission-application-v9-'))

            application.pdf_file.delete(save=True)
            application.student_photo.delete(save=True)
            missing_photo = self.client.get(
                reverse('admin:main_app_admissionapplication_student_photo', args=[application.pk])
            )
            self.assertEqual(missing_photo.status_code, 404)
            regenerated = self.client.get(
                reverse('admin:main_app_admissionapplication_download_pdf', args=[application.pk])
            )
            regenerated_pdf = b''.join(regenerated.streaming_content)
            regenerated.close()
            application.refresh_from_db()
            self.assertEqual(regenerated.status_code, 200)
            self.assertTrue(regenerated_pdf.startswith(b'%PDF-'))
            self.assertTrue(application.pdf_file.storage.exists(application.pdf_file.name))

            status_response = self.client.post(
                reverse('admission_status_lookup'),
                {'application_id': application.application_id, 'email': application.email},
            )
            self.assertContains(status_response, application.application_id)
            self.assertContains(status_response, 'ভর্তি অনুমোদিত')
            self.assertContains(status_response, 'result-grid')
            self.assertContains(status_response, 'আবেদনের বর্তমান অবস্থা')
            self.assertContains(status_response, reverse('admission_status_pdf'))
            status_pdf = self.client.get(reverse('admission_status_pdf'))
            status_pdf_bytes = b''.join(status_pdf.streaming_content)
            status_pdf.close()
            self.assertEqual(status_pdf.status_code, 200)
            self.assertEqual(status_pdf['Content-Type'], 'application/pdf')
            self.assertIn('inline', status_pdf['Content-Disposition'])
            self.assertTrue(status_pdf_bytes.startswith(b'%PDF-'))
            status_pdf_download = self.client.get(
                reverse('admission_status_pdf'),
                {'download': '1'},
            )
            self.assertIn('attachment', status_pdf_download['Content-Disposition'])
            self.assertIn('test-student-class-6-2027.pdf', status_pdf_download['Content-Disposition'])
            status_pdf_download.close()
            private_status_response = self.client.post(
                reverse('admission_status_lookup'),
                {'application_id': application.application_id, 'email': 'wrong@example.com'},
            )
            self.assertContains(private_status_response, 'আবেদন পাওয়া যায়নি')
            self.assertNotContains(private_status_response, 'ভর্তি অনুমোদিত')
            self.assertEqual(self.client.get(reverse('admission_status_pdf')).status_code, 404)


class MediaServingTests(SimpleTestCase):
    def test_media_files_are_served_from_media_root(self):
        media_root = os.path.join(os.getcwd(), 'media')
        media_path = os.path.join(media_root, 'gallery', 'photos')
        os.makedirs(media_path, exist_ok=True)
        image_path = os.path.join(media_path, 'example.jpg')
        with open(image_path, 'wb') as fh:
            fh.write(b'fake-image-data')

        try:
            response = self.client.get('/media/gallery/photos/example.jpg')
        finally:
            if os.path.exists(image_path):
                try:
                    os.remove(image_path)
                except PermissionError:
                    pass

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), b'fake-image-data')


class GalleryAdminTests(TestCase):
    def test_admin_can_save_gallery_category_with_uploaded_images(self):
        user = get_user_model().objects.create_superuser('gallery_admin', 'gallery@example.com', 'secret123')
        self.client.force_login(user)

        cover_image = BytesIO()
        Image.new('RGB', (20, 20), color='green').save(cover_image, format='JPEG')
        cover_image.seek(0)

        inline_image = BytesIO()
        Image.new('RGB', (20, 20), color='red').save(inline_image, format='JPEG')
        inline_image.seek(0)

        response = self.client.post(
            reverse('admin:main_app_gallerycategory_add'),
            data={'name': 'Summer Fair'},
            files={
                'cover_image': SimpleUploadedFile('cover.jpg', cover_image.getvalue(), content_type='image/jpeg'),
                'gallery_images': SimpleUploadedFile('gallery-1.jpg', inline_image.getvalue(), content_type='image/jpeg'),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        category = GalleryCategory.objects.filter(name='Summer Fair').first()
        self.assertIsNotNone(category)
        self.assertTrue(GalleryImage.objects.filter(category=category).exists())


class CommitteePageTests(TestCase):
    def test_committee_page_shows_fixed_categories_and_member_details(self):
        CommitteeMember.objects.create(
            category='PRESIDENT',
            name='কমিটির সভাপতি',
            designation='সভাপতি',
            phone='01700000000',
            about='সভাপতি সম্পর্কে তথ্য',
        )

        response = self.client.get(reverse('committee_page'))

        self.assertEqual(response.status_code, 200)
        for _, category_name in CommitteeMember.CATEGORY_CHOICES:
            self.assertContains(response, category_name)
        self.assertContains(response, 'কমিটির সভাপতি')
        self.assertContains(response, '01700000000')
        self.assertContains(response, 'সভাপতি সম্পর্কে তথ্য')

    def test_committee_members_have_a_separate_admin_entry(self):
        user = get_user_model().objects.create_superuser('committee_admin', 'committee@example.com', 'secret123')
        self.client.force_login(user)

        response = self.client.get(reverse('admin:main_app_committeemember_add'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="category"')
        self.assertContains(response, 'name="name"')
        self.assertContains(response, 'name="designation"')
        self.assertContains(response, 'name="phone"')
        self.assertContains(response, 'name="about"')
        self.assertContains(response, 'name="image"')
        for _, category_name in CommitteeMember.CATEGORY_CHOICES:
            self.assertContains(response, category_name)

    def test_admin_can_upload_committee_member_photo_and_details(self):
        user = get_user_model().objects.create_superuser('committee_uploader', 'uploader@example.com', 'secret123')
        self.client.force_login(user)
        image_buffer = BytesIO()
        Image.new('RGB', (20, 20), color='blue').save(image_buffer, format='JPEG')
        uploaded_image = SimpleUploadedFile('member.jpg', image_buffer.getvalue(), content_type='image/jpeg')

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                response = self.client.post(
                    reverse('admin:main_app_committeemember_add'),
                    data={
                        'category': 'PRESIDENT',
                        'name': 'আপলোড করা সদস্য',
                        'designation': 'সভাপতি',
                        'phone': '01800000000',
                        'about': 'কমিটির সদস্যের পরিচিতি',
                        'order': '0',
                        'image': uploaded_image,
                    },
                    follow=True,
                )

                self.assertEqual(response.status_code, 200)
                member = CommitteeMember.objects.get(name='আপলোড করা সদস্য')
                self.assertEqual(member.phone, '01800000000')
                self.assertEqual(member.about, 'কমিটির সদস্যের পরিচিতি')
                self.assertTrue(member.image.storage.exists(member.image.name))


class LeadershipProfileFormTests(TestCase):
    def test_designation_defaults_from_profile_type_but_allows_override(self):
        image_buffer = BytesIO()
        Image.new('RGB', (20, 20), color='purple').save(image_buffer, format='JPEG')
        upload = SimpleUploadedFile('leader.jpg', image_buffer.getvalue(), content_type='image/jpeg')

        form = LeadershipProfileForm(
            data={
                'profile_type': 'HEADMASTER',
                'name': 'প্রধান শিক্ষক',
                'designation': '',
                'caption': 'শুভেচ্ছা',
            },
            files={'image': upload},
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['designation'], 'প্রধান শিক্ষক')

        override_form = LeadershipProfileForm(
            data={
                'profile_type': 'PRESIDENT',
                'name': 'সভাপতি',
                'designation': 'ব্যক্তিগত পদবি',
                'caption': 'সদয়',
            },
            files={'image': upload},
        )

        self.assertTrue(override_form.is_valid(), override_form.errors)
        self.assertEqual(override_form.cleaned_data['designation'], 'ব্যক্তিগত পদবি')


class NoticeLinkTests(TestCase):
    def setUp(self):
        media_directory = tempfile.TemporaryDirectory()
        self.addCleanup(media_directory.cleanup)
        media_settings = override_settings(MEDIA_ROOT=media_directory.name)
        media_settings.enable()
        self.addCleanup(media_settings.disable)

    def create_notice(self, **kwargs):
        title = kwargs.pop('title', 'গুরুত্বপূর্ণ নোটিশ')
        kwargs.setdefault('show_on_ticker', True)
        return Notice.objects.create(
            title=title,
            description='নোটিশের বিস্তারিত',
            file=SimpleUploadedFile('notice.pdf', b'%PDF-1.4 test notice'),
            **kwargs,
        )

    def test_ticker_notice_title_links_to_its_detail_page(self):
        notice = self.create_notice()

        response = self.client.get(reverse('all_notices'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'href="{reverse("notice_detail", args=[notice.pk])}">{notice.title}</a>',
        )

    def test_notice_detail_shows_download_link_and_file(self):
        notice = self.create_notice()

        response = self.client.get(reverse('notice_detail', args=[notice.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, notice.title)
        self.assertContains(response, notice.description)
        self.assertContains(
            response,
            f'href="{reverse("notice_download", args=[notice.pk])}"',
        )
        self.assertContains(response, notice.file.url)

    def test_notice_download_returns_file_as_attachment(self):
        notice = self.create_notice()

        response = self.client.get(reverse('notice_download', args=[notice.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('notice.pdf', response['Content-Disposition'])
        self.assertEqual(b''.join(response.streaming_content), b'%PDF-1.4 test notice')

    def test_inactive_notice_is_not_publicly_accessible(self):
        notice = self.create_notice(is_active=False)

        response = self.client.get(reverse('notice_detail', args=[notice.pk]))

        self.assertEqual(response.status_code, 404)

    def test_admin_can_select_new_notice_flag(self):
        user = get_user_model().objects.create_superuser('notice_admin', 'notice@example.com', 'secret123')
        self.client.force_login(user)

        response = self.client.get(reverse('admin:main_app_notice_add'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="is_new"')
        self.assertContains(response, 'নতুন নোটিশ?')

    def test_homepage_shows_new_badge_for_marked_dashboard_notices(self):
        self.create_notice(title='নতুন নোটিশ', show_on_dashboard=True, is_new=True, show_on_ticker=False)
        self.create_notice(title='সাধারণ নোটিশ', show_on_dashboard=True, is_new=False, show_on_ticker=False)
        self.create_notice(title='বোর্ডে দেখাবে না', show_on_dashboard=False, is_new=True, show_on_ticker=False)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'নতুন নোটিশ')
        self.assertContains(response, 'সাধারণ নোটিশ')
        self.assertNotContains(response, 'বোর্ডে দেখাবে না')
        self.assertEqual(response.content.decode().count('NEW</span>'), 1)

    def test_homepage_keeps_notice_board_compact_without_blank_space(self):
        for number in range(10):
            self.create_notice(
                title=f'বোর্ড নোটিশ {number + 1}',
                show_on_dashboard=True,
                show_on_ticker=False,
            )

        response = self.client.get(reverse('home'))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('notice-rows-viewport is-scrolling', content)
        self.assertLessEqual(content.count('class="notice-row notice-row-plain"'), 7)
        self.assertIn('.notice-table thead th:nth-child(2) { text-align: center; }', content)

    def test_seven_homepage_items_fit_without_scrolling(self):
        for number in range(7):
            self.create_notice(
                title=f'বোর্ড নোটিশ {number + 1}',
                show_on_dashboard=True,
                show_on_ticker=False,
            )

        response = self.client.get(reverse('home'))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('notice-rows-viewport is-scrolling', content)
        self.assertLessEqual(content.count('class="notice-row notice-row-plain"'), 7)


class WelcomeSliderTests(TestCase):
    def setUp(self):
        media_directory = tempfile.TemporaryDirectory()
        self.addCleanup(media_directory.cleanup)
        media_settings = override_settings(MEDIA_ROOT=media_directory.name)
        media_settings.enable()
        self.addCleanup(media_settings.disable)

    def make_image(self, name='welcome.jpg', color='purple'):
        image_buffer = BytesIO()
        Image.new('RGB', (40, 30), color=color).save(image_buffer, format='JPEG')
        return SimpleUploadedFile(name, image_buffer.getvalue(), content_type='image/jpeg')

    def test_homepage_only_includes_active_images_in_display_order(self):
        later = EntryPopupImage.objects.create(
            title='দ্বিতীয় ঘোষণা',
            image=self.make_image('second.jpg'),
            order=2,
        )
        inactive = EntryPopupImage.objects.create(
            title='নিষ্ক্রিয় ঘোষণা',
            image=self.make_image('inactive.jpg'),
            is_active=False,
            order=0,
        )
        first = EntryPopupImage.objects.create(
            title='প্রথম ঘোষণা',
            image=self.make_image('first.jpg'),
            order=1,
        )

        response = self.client.get(reverse('home'))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertLess(content.index(first.image.url), content.index(later.image.url))
        self.assertIn(first.image.url, content)
        self.assertIn(later.image.url, content)
        self.assertNotIn(inactive.image.url, content)

    def test_homepage_does_not_render_popup_without_active_images(self):
        EntryPopupImage.objects.create(
            title='নিষ্ক্রিয় ঘোষণা',
            image=self.make_image(),
            is_active=False,
        )

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="welcomeSlider"')

    def test_homepage_stays_available_when_an_uploaded_file_is_missing(self):
        image = EntryPopupImage.objects.create(image=self.make_image())
        image.image.storage.delete(image.image.name)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="welcomeSlider"')
        self.assertContains(response, image.image.url)

    def test_admin_has_a_separate_welcome_slider_and_image_preview(self):
        image = EntryPopupImage.objects.create(
            title='প্রবেশ বিজ্ঞপ্তি',
            image=self.make_image('notice.jpg'),
        )
        user = get_user_model().objects.create_superuser(
            'welcome_admin',
            'welcome@example.com',
            'secret123',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('admin:main_app_entrypopupimage_changelist'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Welcome Slider')
        self.assertContains(response, image.image.url)
        self.assertContains(response, 'notice.jpg')

    def test_admin_rejects_invalid_image_upload(self):
        user = get_user_model().objects.create_superuser(
            'welcome_upload_admin',
            'welcome-upload@example.com',
            'secret123',
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse('admin:main_app_entrypopupimage_add'),
            data={
                'title': 'ভুল ফাইল',
                'is_active': 'on',
                'order': '0',
                'image': SimpleUploadedFile(
                    'not-an-image.jpg',
                    b'invalid image data',
                    content_type='image/jpeg',
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(EntryPopupImage.objects.filter(title='ভুল ফাইল').exists())
        self.assertContains(response, 'Upload a valid image')