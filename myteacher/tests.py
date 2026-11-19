from decimal import Decimal
from types import SimpleNamespace
import datetime

from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.signing import TimestampSigner
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from django.contrib import admin

from myteacher.admin import ExamRoutineAdminForm, SubjectAdmin, SubjectAdminForm
from myteacher.models import ExamRoutine, Mark, Subject, Teacher, TeacherSubjectAssignment, Testimonial
from myteacher.views import get_student_result_summary, mark_entry_view
from students.models import ManualASRBatch, Student, StudentResultPublication


class DashboardWithoutTeacherProfileTests(TestCase):
    def test_superuser_without_teacher_profile_gets_admin_dashboard(self):
        user = get_user_model().objects.create_superuser(
            username='school-admin',
            email='admin@example.com',
            password='test-password',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('myteacher:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'School Administration')
        self.assertContains(response, reverse('sms_management:dashboard'))

    def test_regular_user_without_teacher_profile_is_forbidden(self):
        user = get_user_model().objects.create_user(
            username='student-user',
            password='test-password',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('myteacher:dashboard'))

        self.assertEqual(response.status_code, 403)


class TestimonialSavedRecordsTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username='testimonial-headmaster',
            password='test-password',
        )
        self.user = user
        Teacher.objects.create(
            user=user,
            teacher_id='TEST-HM-1',
            teacher_name='Headmaster',
            designation='Headmaster',
            mobile='01700000000',
            email='testimonial-headmaster@example.com',
            teacher_img='',
            assigned_class='10',
        )
        self.client.force_login(user)
        self.student = Student.objects.create(
            full_name='Testimonial Student',
            father_name='Student Father',
            mother_name='Student Mother',
            student_id='TEST101',
            current_class='10',
            class_roll=12,
            shift='Day',
            mobile_num='01700000000',
        )
        self.testimonial = Testimonial.objects.create(
            student=self.student,
            serial_number=21,
            generated_date=datetime.date(2025, 6, 1),
            name='Saved Testimonial Name',
            father_name='Saved Father',
            mother_name='Saved Mother',
            class_level='10',
            group='Science',
            roll='12',
            registration='REG-12',
            session='2024-2025',
            date_of_birth='01/01/2008',
            gender='Female',
            candidate_type='Regular',
        )

    def test_saved_testimonials_are_listed_and_selecting_one_loads_saved_values(self):
        response = self.client.get(
            reverse('myteacher:testimonial'),
            {'student_id': self.student.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Saved Testimonials')
        self.assertContains(response, f'value="{self.student.pk}" selected')
        self.assertContains(response, 'Saved Testimonial Name')
        self.assertContains(response, 'value="Saved Father"')
        self.assertContains(response, 'value="Saved Mother"')
        self.assertContains(response, reverse('myteacher:testimonial_blank', args=['current']))
        self.assertContains(response, reverse('myteacher:testimonial_blank', args=['ssc_passed']))

    def test_saving_an_existing_testimonial_edits_instead_of_duplicating(self):
        response = self.client.post(
            reverse('myteacher:testimonial'),
            {
                'student_id': self.student.pk,
                'name': 'Edited Testimonial Name',
                'father_name': 'Edited Father',
                'mother_name': 'Edited Mother',
                'class_level': '10',
                'group': 'Science',
                'roll': '13',
                'registration': 'REG-13',
                'session': '2024-2025',
                'date_of_birth': '01/01/2008',
                'gender': 'Female',
                'status': 'current',
                'ssc_year': '',
                'ssc_board': '',
                'candidate_type': 'Regular',
                'gpa': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.testimonial.refresh_from_db()
        self.assertEqual(Testimonial.objects.count(), 1)
        self.assertEqual(self.testimonial.name, 'Edited Testimonial Name')
        self.assertEqual(self.testimonial.serial_number, 21)
        self.assertContains(response, '&ldquo;I wish her every success in life.&rdquo;')
        self.assertNotContains(response, 'Student ID: <strong>')
        self.assertNotContains(response, 'Compared by')

    def test_blank_testimonial_print_pages_support_each_student_status(self):
        for status in ('current', 'ssc_passed'):
            with self.subTest(status=status):
                response = self.client.get(reverse(
                    'myteacher:testimonial_blank',
                    args=[status],
                ))

                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context['print_only'])
                self.assertTrue(response.context['blank_template'])
                self.assertEqual(response.context['blank_status'], status)
                self.assertContains(response, 'Print / Save PDF')
                self.assertNotContains(response, 'A Chrome or Edge browser is required')

        self.assertEqual(Testimonial.objects.count(), 1)

    def test_blank_testimonial_templates_have_status_specific_text_and_handwriting_lines(self):
        current_html = render_to_string('myteacher/testimonial.html', {
            'generated': True,
            'blank_template': True,
            'blank_status': 'current',
            'values': {},
        })
        ssc_html = render_to_string('myteacher/testimonial.html', {
            'generated': True,
            'blank_template': True,
            'blank_status': 'ssc_passed',
            'values': {},
        })

        self.assertIn('is a student of Class', current_html)
        self.assertNotIn('passed the Secondary School Certificate', current_html)
        self.assertIn('passed the Secondary School Certificate', ssc_html)
        self.assertIn('class="handwrite-field field-name"', ssc_html)
        self.assertIn('class="handwrite-field field-date"', current_html)

    def test_saved_testimonial_pdf_route_opens_browser_print_page(self):
        token = TimestampSigner().sign_object({
            'user_id': self.user.pk,
            'student_id': self.student.pk,
        })

        response = self.client.get(
            reverse('myteacher:testimonial_pdf'),
            {'token': token},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['print_only'])
        self.assertContains(response, self.testimonial.name)
        self.assertContains(response, 'Print / Save PDF')
        self.assertNotContains(response, 'A Chrome or Edge browser is required')

    def test_non_headmaster_cannot_open_blank_testimonial_print_page(self):
        user = get_user_model().objects.create_user(
            username='regular-testimonial-user',
            password='test-password',
        )
        self.client.force_login(user)

        response = self.client.get(reverse(
            'myteacher:testimonial_blank',
            args=['current'],
        ))

        self.assertEqual(response.status_code, 403)


class IDCardTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username='headmaster-id-card',
            password='test-password',
        )
        Teacher.objects.create(
            user=user,
            teacher_id='HM-ID-1',
            teacher_name='Headmaster',
            designation='Headmaster',
            mobile='01700000000',
            email='headmaster-id@example.com',
            teacher_img='',
            assigned_class='7',
        )
        self.client.force_login(user)

    def test_id_card_shows_two_sides_and_expiry_defaults_to_year_end(self):
        student = Student.objects.create(
            photo='students/card-photo.jpg',
            full_name='Card Test Student',
            father_name='Father Test',
            mother_name='Mother Test',
            student_id='7775364',
            date_of_birth=None,
            blood_group='',
            current_class='7',
            class_roll=21,
            shift='Day',
            mobile_num='01714939123',
            group='Science',
        )

        response = self.client.get(reverse('myteacher:id_cards'), {'class_level': '7'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Back to Student Corner')
        self.assertContains(response, reverse('myteacher:student_corner'))
        self.assertContains(response, f'id="card-front-{student.pk}"')
        self.assertContains(response, f'id="card-back-{student.pk}"')
        self.assertContains(response, 'width: 210px; min-width: 210px; max-width: 210px;')
        self.assertContains(response, 'height: 332px; min-height: 332px; max-height: 332px;')
        self.assertContains(response, 'white-space: nowrap;')
        self.assertContains(response, '<span class="name-text">Card Test Student</span>')
        self.assertContains(response, 'Khondoker Naser Uddin<br>High School')
        self.assertContains(response, 'height: 54px; box-sizing: border-box; display: flex; align-items: center; gap: 4px;')
        self.assertContains(response, 'font-size: 10.5px; font-weight: 900; line-height: 1.05;')
        self.assertContains(response, 'font-size: 10pt; font-weight: 900; line-height: 1.08;')
        self.assertContains(response, 'font-size: var(--card-font-size, 7.2pt);')
        self.assertContains(response, '<option value="7.2pt" selected>Normal</option>')
        self.assertContains(response, 'width: 60px; min-width: 60px; font-weight: 800; white-space: nowrap;')
        self.assertContains(response, 'background: var(--label-badge-bg, var(--maroon));')
        self.assertContains(response, 'border-radius: 999px;')
        self.assertContains(response, 'top: 0; left: 0;')
        self.assertContains(response, 'width: 100%; height: 76px;')
        self.assertContains(response, 'border-radius: 0 0 50% 50% / 0 0 18% 18%;')
        self.assertContains(response, 'top: 58px; left: 0;')
        self.assertContains(response, 'width: 100%; height: 22px;')
        self.assertContains(response, 'border-radius: 0 0 50% 50% / 0 0 72% 72%;')
        self.assertContains(response, 'display: flex; justify-content: center; margin: -10px 0 1px;')
        self.assertContains(response, 'Blood Group')
        self.assertNotContains(response, 'A HOME OF QUALITY')
        self.assertContains(response, '--card-font: "Times New Roman", Times, serif;')
        self.assertContains(response, '-webkit-line-clamp: 2;')
        self.assertContains(response, 'font-size: 8.2pt; font-weight: 800; line-height: 1.15;')
        self.assertContains(response, 'width: 38px; height: auto; object-fit: contain;')
        self.assertContains(response, 'transform: translateY(-4px);')
        self.assertContains(response, 'src="/static/images/sign-cropped.png"')
        self.assertContains(response, "signature.style.transform = 'translateY(-4px)';")
        self.assertContains(response, 'scale: 8,')
        self.assertContains(response, 'card.classList.contains(\'id-card-front\')')
        self.assertContains(response, 'linear-gradient(12deg, ${primaryColor} 0 67%, ${sloganBg} 67% 73%, transparent 73%)')
        self.assertContains(response, 'font-size: 6.5pt; font-weight: 800;')
        self.assertContains(response, '.sig-text + .sig-text { margin-top: 1px; }')
        self.assertEqual(response.content.count(b'class="card-watermark"'), 1)
        self.assertContains(response, 'Card Test Student')
        self.assertContains(response, 'N/A')
        self.assertContains(response, 'Guardian Mobile')
        self.assertEqual(response.content.count(b'class="back-family-row parent-name-row"'), 2)
        self.assertContains(response, '.back-family-row.parent-name-row { height: 19px; overflow: hidden; }')
        self.assertContains(response, '01714939123')
        self.assertContains(response, 'knuhighschool1994@gmail.com')
        self.assertContains(response, f'data-student-name="{student.full_name}"')
        self.assertContains(response, f'data-student-father="{student.father_name}"')
        self.assertContains(response, f'data-student-mother="{student.mother_name}"')
        self.assertContains(response, f'data-student-class="{student.current_class}"')
        self.assertContains(response, 'School Phone: 01714939122&nbsp;|&nbsp;Email: knuhighschool1994@gmail.com')
        self.assertContains(response, 'qrcodejs/1.0.0/qrcode.min.js')
        self.assertContains(response, 'Website: https://knuhighschool.pythonanywhere.com/')
        self.assertContains(response, 'https://knuhighschool.pythonanywhere.com/')
        card_html = response.content.decode()
        qr_content_start = card_html.index('const qrContent = [')
        qr_content_end = card_html.index('].join', qr_content_start)
        qr_content = card_html[qr_content_start:qr_content_end]
        self.assertLess(qr_content.index('School: Khondoker Naser Uddin High School'), qr_content.index('Student:'))
        self.assertLess(qr_content.index('Student:'), qr_content.index('Father:'))
        self.assertLess(qr_content.index('Father:'), qr_content.index('Mother:'))
        self.assertLess(qr_content.index('Mother:'), qr_content.index('Class:'))
        self.assertLess(qr_content.index('Class:'), qr_content.index('Phone: 01714939122'))
        self.assertLess(qr_content.index('Phone: 01714939122'), qr_content.index('Website:'))
        self.assertLess(card_html.index('<div class="photo-area">'), card_html.index('<div class="id-card-label">'))
        self.assertLess(card_html.index('<div class="id-card-label">'), card_html.index('<span class="name-text">'))
        self.assertLess(card_html.index('<span class="name-text">'), card_html.index('<div class="student-id-text">'))
        self.assertLess(card_html.index('<div class="student-id-text">'), card_html.index('<div class="details-container">'))
        self.assertLess(card_html.index('<div class="header back-header">'), card_html.index('<div class="back-emblem">'))
        self.assertLess(card_html.index('<div class="back-emblem">'), card_html.index("Father's Name"))
        self.assertLess(card_html.index("Father's Name"), card_html.index('Valid Until:'))
        self.assertLess(card_html.index('Valid Until:'), card_html.index('If found, please return'))
        self.assertEqual(
            response.context['default_expiry_date'],
            datetime.date(datetime.date.today().year, 12, 31),
        )

    def test_front_header_uses_full_width_palette_and_overlapping_photo(self):
        Student.objects.create(
            full_name='Header Layout Student',
            father_name='Father',
            mother_name='Mother',
            student_id='HDR-1',
            date_of_birth=None,
            blood_group='',
            current_class='7',
            class_roll=1,
            shift='Day',
            mobile_num='',
            group='General',
        )
        response = self.client.get(reverse('myteacher:id_cards'), {'class_level': '7'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'width: 100%; height: 76px;')
        self.assertContains(response, 'background: linear-gradient(145deg, var(--card-header-bg1, var(--maroon-dark)), var(--card-header-bg2, var(--maroon)));')
        self.assertContains(response, 'border-radius: 0 0 50% 50% / 0 0 18% 18%;')
        self.assertContains(response, 'top: 58px; left: 0;')
        self.assertContains(response, 'border-radius: 0 0 50% 50% / 0 0 72% 72%;')
        self.assertContains(response, 'margin: -10px 0 1px;')
        self.assertContains(response, 'height: 56px; box-sizing: border-box; background: var(--card-header-bg1, var(--maroon));')
        self.assertContains(response, 'width: 36px; height: 36px; box-sizing: border-box; border-radius: 50%; padding: 2px;')
        self.assertContains(response, 'border-radius: 50%; object-fit: contain;')
        self.assertContains(response, 'display: flex; align-items: flex-start; margin-bottom: 1.5px;')
        card_html = response.content.decode()
        self.assertLess(card_html.index('Headmaster</div>'), card_html.index('MD. SALIM SARDER'))
        self.assertLess(card_html.index('MD. SALIM SARDER'), card_html.index('Mob: 01714939122'))


class StudentPromotionTests(TestCase):
    def create_class_teacher(self, class_level):
        user = get_user_model().objects.create_user(
            username=f'class-teacher-{class_level}',
            password='test-password',
        )
        Teacher.objects.create(
            user=user,
            teacher_id=f'CT-{class_level}',
            teacher_name='Class Teacher',
            designation='Assistant Teacher',
            mobile='01700000000',
            email=f'class-teacher-{class_level}@example.com',
            teacher_img='',
            assigned_class=class_level,
            is_class_teacher=True,
            class_teacher_of=class_level,
        )
        self.client.force_login(user)

    def create_student(self, student_id, class_level):
        return Student.objects.create(
            full_name=f'Student {student_id}',
            father_name='Father',
            mother_name='Mother',
            student_id=student_id,
            current_class=class_level,
            class_roll=1,
            shift='Day',
            mobile_num='01700000000',
        )

    def test_class_10_promotion_archives_student_by_year(self):
        self.create_class_teacher('10')
        student = self.create_student('OLD1001', '10')

        response = self.client.post(
            reverse('myteacher:student_promotion'),
            {'selected_class': '10', 'promote_student': [str(student.pk)]},
        )

        self.assertRedirects(
            response,
            f"{reverse('myteacher:student_promotion')}?selected_class=10",
        )
        student.refresh_from_db()
        self.assertEqual(student.current_class, '10')
        self.assertEqual(student.old_student_year, datetime.date.today().year)

        corner_response = self.client.get(reverse('myteacher:student_corner'))
        self.assertNotContains(corner_response, 'Old Student Details')
        self.assertNotContains(corner_response, student.full_name)
        self.assertEqual(
            self.client.get(reverse('myteacher:old_student_details')).status_code,
            403,
        )

        promotion_response = self.client.get(
            reverse('myteacher:student_promotion'),
            {'selected_class': '10'},
        )
        self.assertNotContains(promotion_response, student.full_name)

    def test_other_class_promotion_still_moves_student_to_next_class(self):
        self.create_class_teacher('9')
        student = self.create_student('PROM901', '9')

        response = self.client.post(
            reverse('myteacher:student_promotion'),
            {'selected_class': '9', 'promote_student': [str(student.pk)]},
        )

        self.assertRedirects(
            response,
            f"{reverse('myteacher:student_promotion')}?selected_class=9",
        )
        student.refresh_from_db()
        self.assertEqual(student.current_class, '10')
        self.assertIsNone(student.old_student_year)


class OldStudentDetailsTests(TestCase):
    def create_teacher(self, designation, username):
        user = get_user_model().objects.create_user(
            username=username,
            password='test-password',
        )
        Teacher.objects.create(
            user=user,
            teacher_id=f'T-{username[-8:]}',
            teacher_name='Test Staff',
            designation=designation,
            mobile='01700000000',
            email=f'{username}@example.com',
            teacher_img='',
            assigned_class='10',
        )
        self.client.force_login(user)

    def test_headmaster_can_view_year_grouped_details_and_print_layout(self):
        self.create_teacher('Headmaster', 'old-student-headmaster')
        student = Student.objects.create(
            photo='students/archived-photo.jpg',
            full_name='Archived Student',
            father_name='Father Detail',
            mother_name='Mother Detail',
            student_id='OLD2025',
            gender='Female',
            date_of_birth=datetime.date(2010, 3, 5),
            blood_group='A+',
            current_class='10',
            class_roll=12,
            shift='Day',
            mobile_num='01712345678',
            group='Science',
            religion='Islam',
            old_student_year=2025,
        )

        response = self.client.get(reverse('myteacher:old_student_details'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, student.full_name)
        self.assertContains(response, student.father_name)
        self.assertContains(response, student.mother_name)
        self.assertContains(response, student.mobile_num)
        self.assertContains(response, '10 Pass Year: 2025')
        self.assertContains(response, 'src="/media/students/archived-photo.jpg"')
        self.assertContains(response, '@page { size: A4 landscape; margin: 9mm; }')
        self.assertContains(response, 'window.print()')

        corner_response = self.client.get(reverse('myteacher:student_corner'))
        self.assertContains(corner_response, reverse('myteacher:old_student_details'))

    def test_non_headmaster_cannot_view_old_student_details(self):
        self.create_teacher('Assistant Headmaster', 'old-student-assistant')

        response = self.client.get(reverse('myteacher:old_student_details'))

        self.assertEqual(response.status_code, 403)
        corner_response = self.client.get(reverse('myteacher:student_corner'))
        self.assertNotContains(corner_response, reverse('myteacher:old_student_details'))


class ManualASRTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username='headmaster-manual-asr',
            password='test-password',
        )
        Teacher.objects.create(
            user=user,
            teacher_id='HM-ASR-1',
            teacher_name='Headmaster',
            designation='Headmaster',
            mobile='01700000000',
            email='headmaster-asr@example.com',
            teacher_img='',
            assigned_class='6',
        )
        self.client.force_login(user)
        self.year = datetime.date.today().year

    def test_selected_class_loads_its_routine_without_student_records(self):
        ExamRoutine.objects.create(
            class_name='7',
            exam_type='Annual Exam',
            exam_year=self.year,
            subject_name='Mathematics',
            subject_code='M701',
            exam_date=datetime.date(self.year, 11, 1),
            exam_time='10:00 AM',
        )

        response = self.client.get(reverse('myteacher:manual_asr'), {
            'action': 'admit',
            'class_level': '7',
            'exam_type': 'Annual Exam',
            'exam_year': self.year,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mathematics')
        self.assertContains(response, "Father's Name")
        self.assertEqual(Student.objects.count(), 0)

    def test_admit_and_seat_cards_render_with_optional_fields_and_photo_blank(self):
        common_data = {
            'class_level': '7',
            'exam_type': 'Annual Exam',
            'exam_year': str(self.year),
            'full_name': 'Manual Student',
            'student_id': '',
            'father_name': '',
            'mother_name': '',
            'class_roll': '',
            'religion': '',
            'student_religion': '',
            'group': '',
        }
        for action, expected_text in (('admit', 'ADMIT CARD'), ('seat', 'Print Seat Plan')):
            response = self.client.post(reverse('myteacher:manual_asr'), {
                **common_data,
                'action': action,
            })
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, expected_text)
            self.assertContains(response, 'MANUAL STUDENT' if action == 'admit' else 'Manual Student')
        self.assertEqual(Student.objects.count(), 0)

    def test_manual_seat_plan_only_shows_requested_fields_and_saves_section_session(self):
        form_response = self.client.get(reverse('myteacher:manual_asr'), {
            'action': 'seat',
            'class_level': '7',
            'exam_type': 'Annual Exam',
            'exam_year': self.year,
        })
        self.assertEqual(form_response.status_code, 200)
        self.assertContains(form_response, 'Student ID')
        self.assertContains(form_response, 'Section')
        self.assertContains(form_response, 'Session')
        self.assertNotContains(form_response, "Father's Name")
        self.assertNotContains(form_response, "Mother's Name")
        self.assertNotContains(form_response, 'Religion')

        response = self.client.post(reverse('myteacher:manual_asr'), {
            'action': 'seat',
            'class_level': '7',
            'exam_type': 'Annual Exam',
            'exam_year': str(self.year),
            'full_name': 'Manual Seat Student',
            'student_id': '7775364',
            'class_roll': '21',
            'section': 'A',
            'student_session': '2025',
            'student_group': 'General',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Manual Seat Student')
        self.assertContains(response, 'class="exam-info"')
        self.assertContains(response, f'Exam: Annual Exam-{self.year}')
        self.assertContains(response, '7775364')
        self.assertContains(response, 'Section')
        self.assertContains(response, 'Session')
        self.assertContains(response, ': 2025')
        self.assertContains(response, 'SL: 001')
        self.assertContains(response, 'Headmaster')
        self.assertContains(response, 'Khondoker Naser Uddin High School')
        self.assertContains(response, 'Hazi Foyez Uddin Cross Road, Boyra, GPO-9000, Khulna')
        self.assertContains(response, 'class="watermark"')
        self.assertContains(response, 'student-photo-placeholder')
        self.assertNotContains(response, "Father's Name")
        self.assertNotContains(response, "Mother's Name")
        self.assertNotContains(response, 'Religion')
        entry = ManualASRBatch.objects.get(action='seat').students.get()
        self.assertEqual(entry.section, 'A')
        self.assertEqual(entry.session, '2025')

        saved_response = self.client.get(reverse(
            'myteacher:manual_asr_saved_student_print',
            args=[entry.batch_id, entry.pk],
        ))
        self.assertContains(saved_response, ': A')
        self.assertContains(saved_response, ': 2025')

    def test_multiple_students_use_existing_seat_and_admit_page_counts(self):
        base_data = {
            'class_level': '7',
            'exam_type': 'Annual Exam',
            'exam_year': str(self.year),
            'full_name': [f'Manual Student {number}' for number in range(1, 10)],
        }

        seat_response = self.client.post(reverse('myteacher:manual_asr'), {
            **base_data,
            'action': 'seat',
        })
        self.assertEqual(seat_response.status_code, 200)
        self.assertEqual(seat_response.content.count(b'class="seat-card"'), 9)
        self.assertEqual(seat_response.content.count(b'<div class="page">'), 2)

        admit_response = self.client.post(reverse('myteacher:manual_asr'), {
            **base_data,
            'full_name': ['Manual Student 1', 'Manual Student 2', 'Manual Student 3'],
            'action': 'admit',
        })
        self.assertEqual(admit_response.status_code, 200)
        self.assertEqual(admit_response.content.count(b'class="admit-card"'), 3)
        self.assertEqual(admit_response.content.count(b'<div class="page">'), 2)
        self.assertEqual(Student.objects.count(), 0)

        seat_batch = ManualASRBatch.objects.get(action='seat')
        saved_page = self.client.get(reverse('myteacher:manual_asr_saved'))
        self.assertEqual(saved_page.status_code, 200)
        self.assertContains(saved_page, 'Manual Student 1')
        saved_all = self.client.get(reverse(
            'myteacher:manual_asr_saved_print',
            args=[seat_batch.pk],
        ))
        self.assertEqual(saved_all.status_code, 200)
        self.assertEqual(saved_all.content.count(b'class="seat-card"'), 9)

        one_student = seat_batch.students.first()
        saved_single = self.client.get(reverse(
            'myteacher:manual_asr_saved_student_print',
            args=[seat_batch.pk, one_student.pk],
        ))
        self.assertEqual(saved_single.status_code, 200)
        self.assertEqual(saved_single.content.count(b'class="seat-card"'), 1)

    def test_database_seat_plan_shows_only_requested_fields_eight_per_page(self):
        students = [
            Student.objects.create(
                photo='students/seat-plan-test.jpg',
                full_name=f'Database Seat Student {number}',
                father_name='Private Father',
                mother_name='Private Mother',
                student_id=f'800000{number}',
                current_class='7',
                class_roll=number,
                mobile_num='01700000000',
                group='Science',
                religion='Islam',
            )
            for number in range(1, 10)
        ]

        response = self.client.post(reverse('myteacher:generate_seat_plan'), {
            'student_ids': [str(student.pk) for student in students],
            'exam_name': 'Annual Exam',
            'exam_year': str(self.year),
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.count(b'class="seat-card"'), 9)
        self.assertEqual(response.content.count(b'<div class="page">'), 2)
        self.assertContains(response, 'Database Seat Student 1')
        self.assertContains(response, 'Student ID')
        self.assertContains(response, 'Roll No')
        self.assertContains(response, 'class="exam-info"')
        self.assertContains(response, f'Exam: Annual Exam-{self.year}')
        self.assertContains(response, f': {self.year}')
        self.assertContains(response, 'SL: 001')
        self.assertContains(response, 'Headmaster')
        self.assertContains(response, 'Khondoker Naser Uddin High School')
        self.assertContains(response, 'Hazi Foyez Uddin Cross Road, Boyra, GPO-9000, Khulna')
        self.assertEqual(response.content.count(b'class="watermark"'), 9)
        self.assertEqual(response.content.count(b'class="student-photo"'), 9)
        self.assertNotContains(response, "Father's Name")
        self.assertNotContains(response, "Mother's Name")
        self.assertNotContains(response, 'Religion')
        self.assertNotContains(response, 'exam-tag')

    def test_database_and_manual_seat_plans_keep_student_sources_separate(self):
        database_student = Student.objects.create(
            photo='students/database-seat-student.jpg',
            full_name='Database Only Seat Student',
            father_name='Database Father',
            mother_name='Database Mother',
            student_id='7654321',
            current_class='7',
            class_roll=1,
            mobile_num='01700000000',
        )
        batch = ManualASRBatch.objects.create(
            created_by=get_user_model().objects.get(username='headmaster-manual-asr'),
            action='seat',
            class_level='7',
            exam_type='Annual Exam',
            exam_name='Annual Exam',
            exam_year=self.year,
        )
        batch.students.create(
            position=1,
            full_name='Manual Only Seat Student',
            student_id='MANUAL-1',
            roll_no='2',
            session=str(self.year),
            group='General',
        )

        manual_response = self.client.get(reverse(
            'myteacher:manual_asr_saved_print',
            args=[batch.pk],
        ))
        self.assertEqual(manual_response.status_code, 200)
        self.assertContains(manual_response, 'Manual Only Seat Student')
        self.assertContains(manual_response, f'Exam: Annual Exam-{self.year}')
        self.assertNotContains(manual_response, 'Database Only Seat Student')

        database_response = self.client.post(reverse('myteacher:generate_seat_plan'), {
            'student_ids': [str(database_student.pk)],
            'exam_name': 'Annual Exam',
            'exam_year': str(self.year),
        })
        self.assertEqual(database_response.status_code, 200)
        self.assertContains(database_response, 'Database Only Seat Student')
        self.assertContains(database_response, f'Exam: Annual Exam-{self.year}')
        self.assertNotContains(database_response, 'Manual Only Seat Student')

    def test_manual_result_uses_subject_marks_without_saving_student(self):
        subject = Subject.objects.create(
            subject_name='Mathematics',
            subject_code='M701',
            subject_type='1',
            religion='None',
            class_level='7',
            has_practical=False,
            full_mark=Decimal('100.00'),
        )

        response = self.client.post(reverse('myteacher:manual_asr'), {
            'action': 'result',
            'class_level': '7',
            'exam_type': 'Annual Exam',
            'exam_year': str(self.year),
            'full_name': ['Manual Result Student', 'Second Manual Result Student'],
            f'mark_0_{subject.pk}_subjective': '75',
            f'mark_0_{subject.pk}_objective': '0',
            f'mark_0_{subject.pk}_practical': '0',
            f'mark_0_{subject.pk}_class_test': '0',
            f'mark_1_{subject.pk}_subjective': '65',
            f'mark_1_{subject.pk}_objective': '0',
            f'mark_1_{subject.pk}_practical': '0',
            f'mark_1_{subject.pk}_class_test': '0',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Manual Result Student')
        self.assertContains(response, 'Second Manual Result Student')
        self.assertContains(response, 'Mathematics 1st')
        self.assertContains(response, 'A')
        self.assertEqual(response.content.count(b'class="manual-result-page"'), 2)
        self.assertEqual(Student.objects.count(), 0)
        self.assertEqual(Mark.objects.count(), 0)
        batch = ManualASRBatch.objects.get(action='result')
        saved_response = self.client.get(reverse(
            'myteacher:manual_asr_saved_print',
            args=[batch.pk],
        ))
        self.assertEqual(saved_response.status_code, 200)
        self.assertContains(saved_response, 'Second Manual Result Student')
        self.assertEqual(saved_response.content.count(b'class="manual-result-page"'), 2)
        saved_single = self.client.get(reverse(
            'myteacher:manual_asr_saved_student_print',
            args=[batch.pk, batch.students.first().pk],
        ))
        self.assertEqual(saved_single.status_code, 200)
        self.assertEqual(saved_single.content.count(b'class="manual-result-page"'), 1)

    def test_non_head_teacher_cannot_open_manual_asr(self):
        user = get_user_model().objects.create_user(
            username='regular-teacher-asr',
            password='test-password',
        )
        Teacher.objects.create(
            user=user,
            teacher_id='T-ASR-1',
            teacher_name='Regular Teacher',
            designation='Assistant Teacher',
            mobile='01700000001',
            email='teacher-asr@example.com',
            teacher_img='',
            assigned_class='6',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('myteacher:manual_asr'))

        self.assertEqual(response.status_code, 403)


class ResultSummarySubjectCodeTests(TestCase):
    def test_result_summary_uses_configured_subject_code(self):
        student = Student.objects.create(
            photo='',
            full_name='Test Student',
            father_name='Test Father',
            mother_name='Test Mother',
            student_id='1234567',
            gender='Male',
            date_of_birth='2008-01-01',
            current_class='6',
            class_roll=1,
            shift='Day',
            mobile_num='01700000000',
            group=None,
            religion='Islam',
        )
        subject = Subject.objects.create(
            subject_name='Bangla 1st',
            subject_code='B101',
            subject_type='1',
            religion='None',
            class_level='6',
            has_practical=False,
            full_mark=Decimal('100.00'),
        )
        Mark.objects.create(
            student=student,
            subject=subject,
            exam_type='Half Yearly',
            exam_year=2026,
            objective_mark=Decimal('30.00'),
            subjective_mark=Decimal('40.00'),
            class_test_mark=Decimal('10.00'),
            practical_mark=Decimal('0.00'),
        )

        summary = get_student_result_summary(student, 'Half Yearly', '2026')

        self.assertEqual(summary['marks'][0]['subject_code'], 'B101')

    def test_optional_subject_failure_renders_as_failing_row(self):
        student = SimpleNamespace(
            full_name='Optional Student',
            father_name='Father',
            mother_name='Mother',
            student_id='1234567',
            current_class='6',
            class_roll=1,
            shift='Day',
            group='Science',
            photo=None,
        )
        result_data = {
            'student': student,
            'marks': [
                {
                    'subject_code': 'B101',
                    'subject_name': 'Bangla 1st',
                    'full_mark': Decimal('100.00'),
                    'subjective_mark': Decimal('40.00'),
                    'objective_mark': Decimal('20.00'),
                    'practical_mark': Decimal('0.00'),
                    'class_test_mark': Decimal('10.00'),
                    'total_mark': Decimal('70.00'),
                    'combined_total_mark': Decimal('70.00'),
                    'gpa': '3.50',
                    'combined_gpa': '3.50',
                    'grade': 'A-',
                    'combined_grade': 'A-',
                    'group_rowspan': 1,
                    'show_combined': True,
                    'optional': False,
                },
                {
                    'subject_code': 'E401',
                    'subject_name': 'English 4th (4th Subject)',
                    'full_mark': Decimal('100.00'),
                    'subjective_mark': Decimal('20.00'),
                    'objective_mark': Decimal('10.00'),
                    'practical_mark': Decimal('0.00'),
                    'class_test_mark': Decimal('0.00'),
                    'total_mark': Decimal('30.00'),
                    'combined_total_mark': Decimal('30.00'),
                    'gpa': '0.00',
                    'combined_gpa': '0.00',
                    'grade': 'F',
                    'combined_grade': 'F',
                    'group_rowspan': 1,
                    'show_combined': True,
                    'optional': True,
                },
            ],
            'total_possible_marks': Decimal('200.00'),
            'total_marks': Decimal('100.00'),
            'overall_gpa': '3.50',
            'overall_grade': 'A-',
            'result_status': 'Pass',
        }
        html = render_to_string('myteacher/result_card_display.html', {
            'result_data': result_data,
            'selected_exam': 'Half Yearly',
            'selected_year': '2026',
        })

        self.assertIn('<tr class="failing-row">', html)

    def test_optional_subject_failure_does_not_change_pass_status_or_bonus(self):
        student = Student.objects.create(
            photo='',
            full_name='Optional Bonus Student',
            father_name='Father',
            mother_name='Mother',
            student_id='7654321',
            gender='Male',
            date_of_birth='2008-01-01',
            current_class='6',
            class_roll=2,
            shift='Day',
            mobile_num='01700000001',
            group=None,
            religion='Islam',
        )
        compulsory_subject = Subject.objects.create(
            subject_name='Bangla 1st',
            subject_code='B101',
            subject_type='1',
            religion='None',
            class_level='6',
            has_practical=False,
            full_mark=Decimal('100.00'),
        )
        optional_subject = Subject.objects.create(
            subject_name='English 4th',
            subject_code='E401',
            subject_type='4',
            religion='None',
            class_level='6',
            has_practical=False,
            full_mark=Decimal('100.00'),
        )
        Mark.objects.create(
            student=student,
            subject=compulsory_subject,
            exam_type='Half Yearly',
            exam_year=2026,
            objective_mark=Decimal('20.00'),
            subjective_mark=Decimal('30.00'),
            class_test_mark=Decimal('0.00'),
            practical_mark=Decimal('0.00'),
        )
        Mark.objects.create(
            student=student,
            subject=optional_subject,
            exam_type='Half Yearly',
            exam_year=2026,
            objective_mark=Decimal('10.00'),
            subjective_mark=Decimal('10.00'),
            class_test_mark=Decimal('0.00'),
            practical_mark=Decimal('0.00'),
        )

        summary = get_student_result_summary(student, 'Half Yearly', '2026')

        self.assertEqual(summary['result_status'], 'Pass')
        self.assertEqual(summary['overall_gpa'], Decimal('3.00'))
        self.assertEqual(summary['optional_benefit'], Decimal('0.00'))

    def test_summary_totals_include_displayed_optional_subjects_but_not_for_gpa(self):
        student = Student.objects.create(
            photo='',
            full_name='Optional Summary Student',
            father_name='Father',
            mother_name='Mother',
            student_id='4000001',
            gender='Male',
            date_of_birth='2008-01-01',
            current_class='6',
            class_roll=4,
            shift='Day',
            mobile_num='01700000014',
            group=None,
            religion='Islam',
        )
        compulsory_subject = Subject.objects.create(
            subject_name='Bangla 1st',
            subject_code='B101',
            subject_type='1',
            religion='None',
            class_level='6',
            has_practical=False,
            full_mark=Decimal('100.00'),
        )
        optional_subject = Subject.objects.create(
            subject_name='English 4th',
            subject_code='E401',
            subject_type='4',
            religion='None',
            class_level='6',
            has_practical=False,
            full_mark=Decimal('100.00'),
        )

        Mark.objects.create(
            student=student,
            subject=compulsory_subject,
            exam_type='Half Yearly',
            exam_year=2026,
            objective_mark=Decimal('20.00'),
            subjective_mark=Decimal('40.00'),
            class_test_mark=Decimal('0.00'),
            practical_mark=Decimal('0.00'),
        )
        Mark.objects.create(
            student=student,
            subject=optional_subject,
            exam_type='Half Yearly',
            exam_year=2026,
            objective_mark=Decimal('30.00'),
            subjective_mark=Decimal('50.00'),
            class_test_mark=Decimal('0.00'),
            practical_mark=Decimal('0.00'),
        )

        summary = get_student_result_summary(student, 'Half Yearly', '2026')

        self.assertEqual(summary['total_possible_marks'], Decimal('200.00'))
        self.assertEqual(summary['total_marks'], Decimal('140.00'))
        # According to business rule, optional bonus must not make overall GPA 5.00
        self.assertTrue(summary['overall_gpa'] < Decimal('5.00'))
        self.assertNotEqual(summary['overall_grade'], 'A+')


    def test_result_summary_includes_highest_mark_in_class(self):
        subject = Subject.objects.create(
            subject_name='Bangla 1st',
            subject_code='B101',
            subject_type='1',
            religion='None',
            class_level='6',
            has_practical=False,
            full_mark=Decimal('100.00'),
        )

        first_student = Student.objects.create(
            photo='',
            full_name='First Student',
            father_name='Father',
            mother_name='Mother',
            student_id='2000001',
            gender='Male',
            date_of_birth='2008-01-01',
            current_class='6',
            class_roll=1,
            shift='Day',
            mobile_num='01700000011',
            group=None,
            religion='Islam',
        )
        second_student = Student.objects.create(
            photo='',
            full_name='Second Student',
            father_name='Father',
            mother_name='Mother',
            student_id='2000002',
            gender='Male',
            date_of_birth='2008-01-01',
            current_class='6',
            class_roll=2,
            shift='Day',
            mobile_num='01700000012',
            group=None,
            religion='Islam',
        )

        for student, total_mark in [(first_student, Decimal('85.00')), (second_student, Decimal('72.00'))]:
            Mark.objects.create(
                student=student,
                subject=subject,
                exam_type='Half Yearly',
                exam_year=2026,
                objective_mark=Decimal('20.00'),
                subjective_mark=total_mark,
                class_test_mark=Decimal('0.00'),
                practical_mark=Decimal('0.00'),
            )

        summary = get_student_result_summary(first_student, 'Half Yearly', '2026')

        self.assertEqual(summary['highest_total_mark_in_class'], Decimal('105.00'))

    def test_result_position_uses_competition_ranking_for_same_class_and_group(self):
        subject = Subject.objects.create(
            subject_name='Bangla 1st',
            subject_code='B101',
            subject_type='1',
            religion='None',
            class_level='6',
            has_practical=False,
            full_mark=Decimal('100.00'),
        )

        first_student = Student.objects.create(
            photo='',
            full_name='First Student',
            father_name='Father',
            mother_name='Mother',
            student_id='1000001',
            gender='Male',
            date_of_birth='2008-01-01',
            current_class='6',
            class_roll=1,
            shift='Day',
            mobile_num='01700000001',
            group=None,
            religion='Islam',
        )
        tied_student = Student.objects.create(
            photo='',
            full_name='Tied Student',
            father_name='Father',
            mother_name='Mother',
            student_id='1000002',
            gender='Male',
            date_of_birth='2008-01-01',
            current_class='6',
            class_roll=2,
            shift='Day',
            mobile_num='01700000002',
            group=None,
            religion='Islam',
        )
        third_student = Student.objects.create(
            photo='',
            full_name='Third Student',
            father_name='Father',
            mother_name='Mother',
            student_id='1000003',
            gender='Male',
            date_of_birth='2008-01-01',
            current_class='6',
            class_roll=3,
            shift='Day',
            mobile_num='01700000003',
            group=None,
            religion='Islam',
        )

        for student, total_mark in [(first_student, Decimal('70.00')), (tied_student, Decimal('70.00')), (third_student, Decimal('60.00'))]:
            Mark.objects.create(
                student=student,
                subject=subject,
                exam_type='Half Yearly',
                exam_year=2026,
                objective_mark=Decimal('20.00'),
                subjective_mark=total_mark,
                class_test_mark=Decimal('0.00'),
                practical_mark=Decimal('0.00'),
            )

        tied_summary = get_student_result_summary(tied_student, 'Half Yearly', '2026')
        third_summary = get_student_result_summary(third_student, 'Half Yearly', '2026')

        self.assertEqual(tied_summary['position'], 1)
        self.assertEqual(tied_summary['position_display'], '1st')
        self.assertEqual(third_summary['position'], 2)
        self.assertEqual(third_summary['position_display'], '2nd')

    def test_failed_students_receive_positions_after_passed_students(self):
        subject = Subject.objects.create(
            subject_name='Bangla 1st',
            subject_code='B101',
            subject_type='1',
            religion='None',
            class_level='6',
            has_practical=False,
            full_mark=Decimal('100.00'),
        )

        passed_student = Student.objects.create(
            photo='',
            full_name='Passed Student',
            father_name='Father',
            mother_name='Mother',
            student_id='3000001',
            gender='Male',
            date_of_birth='2008-01-01',
            current_class='6',
            class_roll=1,
            shift='Day',
            mobile_num='01700000005',
            group=None,
            religion='Islam',
        )
        failed_student = Student.objects.create(
            photo='',
            full_name='Failed Student',
            father_name='Father',
            mother_name='Mother',
            student_id='3000002',
            gender='Male',
            date_of_birth='2008-01-01',
            current_class='6',
            class_roll=2,
            shift='Day',
            mobile_num='01700000006',
            group=None,
            religion='Islam',
        )

        Mark.objects.create(
            student=passed_student,
            subject=subject,
            exam_type='Half Yearly',
            exam_year=2026,
            objective_mark=Decimal('20.00'),
            subjective_mark=Decimal('70.00'),
            class_test_mark=Decimal('0.00'),
            practical_mark=Decimal('0.00'),
        )
        Mark.objects.create(
            student=failed_student,
            subject=subject,
            exam_type='Half Yearly',
            exam_year=2026,
            objective_mark=Decimal('0.00'),
            subjective_mark=Decimal('0.00'),
            class_test_mark=Decimal('0.00'),
            practical_mark=Decimal('0.00'),
        )

        passed_summary = get_student_result_summary(passed_student, 'Half Yearly', '2026')
        failed_summary = get_student_result_summary(failed_student, 'Half Yearly', '2026')

        self.assertEqual(passed_summary['position'], 1)
        self.assertEqual(failed_summary['position'], 2)
        self.assertEqual(failed_summary['position_display'], '2nd')

    def test_position_and_highest_total_consistency_with_optional_subjects(self):
        # Create two students where one has an extra optional subject
        subject_core = Subject.objects.create(
            subject_name='Core Subject',
            subject_code='C101',
            subject_type='1',
            religion='None',
            class_level='6',
            has_practical=False,
            full_mark=Decimal('100.00'),
        )
        optional_subject = Subject.objects.create(
            subject_name='Optional Subject',
            subject_code='O401',
            subject_type='4',
            religion='None',
            class_level='6',
            has_practical=False,
            full_mark=Decimal('100.00'),
        )

        student_a = Student.objects.create(
            photo='',
            full_name='Student A',
            father_name='Father',
            mother_name='Mother',
            student_id='5000001',
            gender='Male',
            date_of_birth='2008-01-01',
            current_class='6',
            class_roll=1,
            shift='Day',
            mobile_num='01700000020',
            group=None,
            religion='Islam',
        )
        student_b = Student.objects.create(
            photo='',
            full_name='Student B',
            father_name='Father',
            mother_name='Mother',
            student_id='5000002',
            gender='Male',
            date_of_birth='2008-01-01',
            current_class='6',
            class_roll=2,
            shift='Day',
            mobile_num='01700000021',
            group=None,
            religion='Islam',
        )

        # Both get same core marks
        Mark.objects.create(student=student_a, subject=subject_core, exam_type='Half Yearly', exam_year=2026, objective_mark=Decimal('30.00'), subjective_mark=Decimal('40.00'), class_test_mark=Decimal('10.00'), practical_mark=Decimal('0.00'))
        Mark.objects.create(student=student_b, subject=subject_core, exam_type='Half Yearly', exam_year=2026, objective_mark=Decimal('30.00'), subjective_mark=Decimal('40.00'), class_test_mark=Decimal('10.00'), practical_mark=Decimal('0.00'))

        # Student A has an optional extra that boosts total
        Mark.objects.create(student=student_a, subject=optional_subject, exam_type='Half Yearly', exam_year=2026, objective_mark=Decimal('25.00'), subjective_mark=Decimal('25.00'), class_test_mark=Decimal('0.00'), practical_mark=Decimal('0.00'))

        summary_a = get_student_result_summary(student_a, 'Half Yearly', '2026')
        summary_b = get_student_result_summary(student_b, 'Half Yearly', '2026')

        # Student A's total should be higher due to optional subject
        self.assertTrue(summary_a['total_marks'] > summary_b['total_marks'])
        # Therefore Student A's position should be 1 and highest_total_in_class should equal Student A's total
        self.assertEqual(summary_a['position'], 1)
        self.assertEqual(summary_a['highest_total_mark_in_class'], summary_a['total_marks'])

    def test_final_gpa_not_five_with_compulsory_non_perfect(self):
        # Compulsory subjects not perfect, optional high score should not force overall GPA to 5.00
        subj1 = Subject.objects.create(
            subject_name='Compulsory 1',
            subject_code='C101',
            subject_type='1',
            religion='None',
            class_level='6',
            has_practical=False,
            full_mark=Decimal('100.00'),
        )
        subj2 = Subject.objects.create(
            subject_name='Compulsory 2',
            subject_code='C102',
            subject_type='1',
            religion='None',
            class_level='6',
            has_practical=False,
            full_mark=Decimal('100.00'),
        )
        optional = Subject.objects.create(
            subject_name='Optional High',
            subject_code='O401',
            subject_type='4',
            religion='None',
            class_level='6',
            has_practical=False,
            full_mark=Decimal('100.00'),
        )

        student = Student.objects.create(
            photo='',
            full_name='GPA Check',
            father_name='Father',
            mother_name='Mother',
            student_id='6000001',
            gender='Male',
            date_of_birth='2008-01-01',
            current_class='6',
            class_roll=10,
            shift='Day',
            mobile_num='01700000010',
            group=None,
            religion='Islam',
        )

        # Give compulsory subjects A (gpa 4.00) each
        Mark.objects.create(student=student, subject=subj1, exam_type='Half Yearly', exam_year=2026, objective_mark=Decimal('30.00'), subjective_mark=Decimal('35.00'), class_test_mark=Decimal('10.00'), practical_mark=Decimal('0.00'))
        Mark.objects.create(student=student, subject=subj2, exam_type='Half Yearly', exam_year=2026, objective_mark=Decimal('30.00'), subjective_mark=Decimal('35.00'), class_test_mark=Decimal('10.00'), practical_mark=Decimal('0.00'))
        # Optional with very high marks (would be gpa 5.00)
        Mark.objects.create(student=student, subject=optional, exam_type='Half Yearly', exam_year=2026, objective_mark=Decimal('45.00'), subjective_mark=Decimal('50.00'), class_test_mark=Decimal('5.00'), practical_mark=Decimal('0.00'))

        summary = get_student_result_summary(student, 'Half Yearly', '2026')

        # Since compulsory average_gpa < 5.00, final overall_gpa must be less than 5.00
        self.assertTrue(isinstance(summary['overall_gpa'], Decimal))
        self.assertTrue(summary['overall_gpa'] < Decimal('5.00'))
        self.assertNotEqual(summary['overall_grade'], 'A+')

    def test_final_submit_keeps_result_unpublished_until_headmaster_toggle(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(username='teacher1', password='secret123')
        teacher = Teacher.objects.create(
            user=user,
            teacher_id='T001',
            teacher_name='Test Teacher',
            designation='Assistant Teacher',
            mobile='01711111111',
            email='teacher1@example.com',
            teacher_img=SimpleUploadedFile('teacher.png', b'img', content_type='image/png'),
            assigned_class='6',
            is_class_teacher=False,
            class_teacher_of=None,
        )
        subject = Subject.objects.create(
            subject_name='Bangla 1st',
            subject_code='B101',
            subject_type='1',
            religion='None',
            class_level='6',
            has_practical=False,
            full_mark=Decimal('100.00'),
        )
        TeacherSubjectAssignment.objects.create(teacher=teacher, subject=subject)
        student = Student.objects.create(
            photo='',
            full_name='Test Student',
            father_name='Test Father',
            mother_name='Test Mother',
            student_id='1234567',
            gender='Male',
            date_of_birth='2008-01-01',
            current_class='6',
            class_roll=1,
            shift='Day',
            mobile_num='01700000000',
            group=None,
            religion='Islam',
        )

        factory = RequestFactory()
        request = factory.post(
            '/myteacher/mark-entry/',
            {
                'subject_id': str(subject.id),
                'class_level': '6',
                'exam_type': 'Half Yearly',
                'exam_year': '2026',
                'final_submit': '1',
                f'obj_{student.id}': '40',
                f'sub_{student.id}': '40',
                f'ct_{student.id}': '20',
            },
        )
        request.user = user
        setattr(request, 'session', {})
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)

        response = mark_entry_view(request)

        self.assertEqual(response.status_code, 302)
        publication = StudentResultPublication.objects.get(
            class_level='6',
            exam_type='Half Yearly',
            exam_year='2026',
        )
        self.assertFalse(publication.is_published)

    def test_user_screenshot_case(self):
        # Reproduce user-provided marks (screenshot) and verify final GPA/grade
        student = Student.objects.create(
            photo='',
            full_name='Screenshot Student',
            father_name='Father',
            mother_name='Mother',
            student_id='6001',
            gender='Male',
            date_of_birth='2008-01-01',
            current_class='9',
            class_roll=1,
            shift='Day',
            mobile_num='01700000060',
            group='General',
            religion='Islam',
        )

        def mk_subject(name, stype, full):
            return Subject.objects.create(
                subject_name=name,
                subject_code=name[:4].upper(),
                subject_type=stype,
                religion='None',
                class_level='9',
                has_practical=False,
                full_mark=Decimal(str(full)),
            )

        s1 = mk_subject('Bangla 1st', '1', 100)
        s2 = mk_subject('Bangla 2nd', '2', 50)
        s3 = mk_subject('English 1st', '1', 100)
        s4 = mk_subject('English 2nd', '2', 50)
        s5 = mk_subject('Agricultural Studies', '4', 50)
        s6 = mk_subject('Bangladesh and Global Studies', '1', 100)
        s7 = mk_subject('Mathematics', '1', 100)
        s8 = mk_subject('Science', '1', 100)

        # Create marks as provided: objective, subjective, class_test, practical
        Mark.objects.create(student=student, subject=s1, exam_type='Annual', exam_year=2025, objective_mark=Decimal('21'), subjective_mark=Decimal('32'), class_test_mark=Decimal('0'), practical_mark=Decimal('0'))
        Mark.objects.create(student=student, subject=s2, exam_type='Annual', exam_year=2025, objective_mark=Decimal('8'), subjective_mark=Decimal('23'), class_test_mark=Decimal('0'), practical_mark=Decimal('0'))
        Mark.objects.create(student=student, subject=s3, exam_type='Annual', exam_year=2025, objective_mark=Decimal('0'), subjective_mark=Decimal('65'), class_test_mark=Decimal('0'), practical_mark=Decimal('0'))
        Mark.objects.create(student=student, subject=s4, exam_type='Annual', exam_year=2025, objective_mark=Decimal('0'), subjective_mark=Decimal('24'), class_test_mark=Decimal('9'), practical_mark=Decimal('0'))
        Mark.objects.create(student=student, subject=s5, exam_type='Annual', exam_year=2025, objective_mark=Decimal('0'), subjective_mark=Decimal('0'), class_test_mark=Decimal('0'), practical_mark=Decimal('36'))
        Mark.objects.create(student=student, subject=s6, exam_type='Annual', exam_year=2025, objective_mark=Decimal('21'), subjective_mark=Decimal('40'), class_test_mark=Decimal('0'), practical_mark=Decimal('0'))
        Mark.objects.create(student=student, subject=s7, exam_type='Annual', exam_year=2025, objective_mark=Decimal('13'), subjective_mark=Decimal('31'), class_test_mark=Decimal('7'), practical_mark=Decimal('0'))
        Mark.objects.create(student=student, subject=s8, exam_type='Annual', exam_year=2025, objective_mark=Decimal('12'), subjective_mark=Decimal('34'), class_test_mark=Decimal('0'), practical_mark=Decimal('0'))

        summary = get_student_result_summary(student, 'Annual', 2025)

        # Print values to test output for manual inspection
        print('\n--- Screenshot Case Summary ---')
        print('Total marks:', summary['total_marks'])
        print('Total possible:', summary['total_possible_marks'])
        print('Overall GPA:', summary['overall_gpa'])
        print('Overall Grade:', summary['overall_grade'])
        print('Result status:', summary['result_status'])
        print('Highest in class:', summary['highest_total_mark_in_class'])
        print('Position:', summary['position'])
        print('--------------------------------')

        # Assertions: optional subject bonus must not force GPA to 5.00
        self.assertTrue(isinstance(summary['overall_gpa'], Decimal))
        self.assertTrue(summary['overall_gpa'] < Decimal('5.00'))
        self.assertNotEqual(summary['overall_grade'], 'A+')


class RoutineSubjectSelectionTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username='routine-teacher', password='test-password')
        Teacher.objects.create(
            user=user,
            teacher_id='RT001',
            teacher_name='Routine Teacher',
            designation='Assistant Teacher',
            mobile='01700000000',
            email='routine-teacher@example.com',
            assigned_class='6',
            teacher_img='',
            is_class_teacher=True,
            class_teacher_of='6',
        )
        self.client.force_login(user)

    def create_subject(self, group_name=''):
        return Subject.objects.create(
            subject_name='Mathematics',
            subject_code='109',
            subject_type='1',
            religion='None',
            class_level='9',
            group_name=group_name,
        )

    def routine_payload(self, subject, group_name='Science'):
        return {
            'save_routine': '1',
            'class_name': '9',
            'group_name': group_name,
            'subject_id': str(subject.pk),
            'date': '2026-10-11',
            'time': '10:00 AM',
            'exam_type': 'Half Yearly',
            'exam_year': '2026',
        }

    def test_routine_uses_subject_name_and_code_from_selected_subject(self):
        subject = self.create_subject('Science')

        response = self.client.post(reverse('myteacher:manage_routine'), self.routine_payload(subject))

        self.assertEqual(response.status_code, 302)
        routine = ExamRoutine.objects.get()
        self.assertEqual(routine.subject_name, 'Mathematics')
        self.assertEqual(routine.subject_code, '109')
        self.assertEqual(routine.group_name, 'Science')

    def test_routine_form_renders_subjects_with_class_and_group_data(self):
        subject = self.create_subject('Science')
        routine_only_subject = self.create_subject('Science')
        routine_only_subject.subject_name = 'Physics Practical'
        routine_only_subject.is_routine_only = True
        routine_only_subject.save()

        response = self.client.get(reverse('myteacher:manage_routine'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'value="{subject.pk}"')
        self.assertContains(response, f'value="{routine_only_subject.pk}"')
        self.assertContains(response, 'Physics Practical')
        self.assertContains(response, 'data-class-level="9"')
        self.assertContains(response, 'data-group-name="Science"')
        self.assertContains(response, 'data-code="109"')

    def test_group_specific_subject_cannot_be_saved_to_another_group(self):
        subject = self.create_subject('Science')
        payload = self.routine_payload(subject, 'Commerce')

        response = self.client.post(reverse('myteacher:manage_routine'), payload)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(ExamRoutine.objects.exists())

    def test_general_routine_is_shown_in_each_class_nine_group(self):
        ExamRoutine.objects.create(
            class_name='9',
            group_name='',
            exam_type='Half Yearly',
            exam_year=2026,
            subject_name='Bangla',
            subject_code='101',
            exam_date='2026-10-11',
        )

        response = self.client.get(reverse('myteacher:view_routine'))
        cells = response.context['date_rows'][0]['cells']

        self.assertEqual([cells[index].subject_name for index in (3, 4, 5)], ['Bangla'] * 3)

    def test_single_class_routine_prints_portrait_with_letterhead_and_signatures(self):
        ExamRoutine.objects.create(
            class_name='9',
            group_name='Science',
            exam_type='Half Yearly',
            exam_year=2026,
            subject_name='Physics',
            subject_code='136',
            exam_date='2026-10-11',
        )

        response = self.client.get(reverse('myteacher:view_routine'), {'classes': ['9']})

        self.assertEqual(response.context['print_orientation'], 'portrait')
        self.assertTrue(response.context['single_class'])
        self.assertContains(response, 'খন্দকার নাসের উদ্দীন মাধ্যমিক বিদ্যালয়')
        self.assertContains(response, 'শ্রেণি শিক্ষক')
        self.assertContains(response, 'প্রধান শিক্ষক')
        self.assertContains(response, 'বিদ্যালয়ের পাওনা পরিশোধ পূর্বক')
        self.assertContains(response, 'size: portrait')

    def test_multiple_class_routine_prints_landscape_without_single_class_signatures(self):
        for class_name, subject_name in [('6', 'Bangla'), ('9', 'Mathematics')]:
            ExamRoutine.objects.create(
                class_name=class_name,
                group_name='' if class_name == '6' else 'Science',
                exam_type='Half Yearly',
                exam_year=2026,
                subject_name=subject_name,
                subject_code='101',
                exam_date='2026-10-11',
            )

        response = self.client.get(
            reverse('myteacher:view_routine'),
            {'classes': ['6', '9']},
        )

        self.assertEqual(response.context['print_orientation'], 'landscape')
        self.assertFalse(response.context['single_class'])
        self.assertContains(response, 'Class 6')
        self.assertContains(response, 'Class 9')
        self.assertNotContains(response, 'শ্রেণি শিক্ষক')
        self.assertContains(response, 'size: landscape')


class RoutineAdminSubjectSelectionTests(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(
            subject_name='Physics',
            subject_code='136',
            subject_type='1',
            religion='None',
            class_level='9',
            group_name='Science',
        )

    def routine_form_data(self, group_name='Science'):
        return {
            'class_name': '9',
            'group_name': group_name,
            'subject_option': str(self.subject.pk),
            'exam_type': 'Half Yearly',
            'exam_year': '2026',
            'exam_date': '2026-10-11',
            'exam_time': '10:00 AM',
        }

    def test_admin_routine_form_saves_subject_name_and_code(self):
        form = ExamRoutineAdminForm(data=self.routine_form_data())

        self.assertTrue(form.is_valid(), form.errors)
        routine = form.save()

        self.assertEqual(routine.subject_name, 'Physics')
        self.assertEqual(routine.subject_code, '136')

    def test_admin_routine_subject_choices_include_class_group_and_code(self):
        form = ExamRoutineAdminForm()
        rendered_subject_field = str(form['subject_option'])

        self.assertIn('Physics (136)', rendered_subject_field)
        self.assertIn('data-class-level="9"', rendered_subject_field)
        self.assertIn('data-group-name="Science"', rendered_subject_field)
        self.assertIn('data-code="136"', rendered_subject_field)

    def test_admin_routine_form_rejects_subject_from_another_group(self):
        form = ExamRoutineAdminForm(data=self.routine_form_data('Commerce'))

        self.assertFalse(form.is_valid())
        self.assertIn('subject_option', form.errors)


class RoutineOnlySubjectAdminTests(TestCase):
    def save_subject_form(self, data):
        form = SubjectAdminForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        subject = form.save(commit=False)
        subject_admin = SubjectAdmin(Subject, admin.site)
        subject_admin.save_model(RequestFactory().post('/admin/myteacher/subject/add/'), subject, form, False)
        return form

    def subject_form_data(self, class_level, group_name='', **extra):
        return {
            'subject_name': 'Physics',
            'subject_code': '136',
            'subject_type': '1',
            'religion': 'None',
            'class_level': class_level,
            'group_name': group_name,
            'has_practical': '',
            'full_mark': '',
            **extra,
        }

    def test_subject_form_has_group_all_and_class_specific_routine_fields(self):
        form = SubjectAdminForm()

        self.assertIn(('ALL', 'All groups (Science, Arts, Commerce)'), form.fields['group_name'].choices)
        self.assertIn('middle_routine_subject', form.fields)
        self.assertIn('senior_routine_subject', form.fields)
        self.assertIn('subject_admin_form.js', str(form.media))

    def test_subject_change_admin_page_renders_existing_routine_subject(self):
        user = get_user_model().objects.create_superuser(
            username='subject-admin',
            email='subject-admin@example.com',
            password='test-password',
        )
        subject = Subject.objects.create(
            subject_name='Bangla',
            subject_code='101',
            subject_type='1',
            class_level='6',
        )
        Subject.objects.create(
            subject_name='Bangla + Practical',
            subject_code='101',
            subject_type='0',
            class_level='6',
            is_routine_only=True,
            routine_parent=subject,
        )
        self.client.force_login(user)

        response = self.client.get(reverse('admin:myteacher_subject_change', args=[subject.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id_middle_routine_subject')
        self.assertContains(response, 'Bangla + Practical')
        self.assertNotContains(response, 'id_senior_routine_subject')

    def test_subject_change_updates_existing_routine_subject(self):
        user = get_user_model().objects.create_superuser(
            username='subject-edit-admin',
            email='subject-edit-admin@example.com',
            password='test-password',
        )
        subject = Subject.objects.create(
            subject_name='Agricultural Studies',
            subject_code='134',
            subject_type='1',
            class_level='7',
        )
        routine_subject = Subject.objects.create(
            subject_name='Agricultural Studies + Practical',
            subject_code='134',
            subject_type='0',
            class_level='7',
            is_routine_only=True,
            routine_parent=subject,
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse('admin:myteacher_subject_change', args=[subject.pk]),
            {
                'subject_name': 'Agricultural Studies',
                'subject_code': '134',
                'subject_type': '1',
                'religion': 'None',
                'class_level': '7',
                'group_name': '',
                'has_practical': '',
                'full_mark': '',
                'middle_routine_subject': 'Agricultural Studies and Practical',
                '_save': 'Save',
            },
        )

        self.assertEqual(response.status_code, 302)
        routine_subject.refresh_from_db()
        self.assertEqual(routine_subject.subject_name, 'Agricultural Studies and Practical')
        self.assertEqual(routine_subject.subject_code, '134')
        self.assertEqual(routine_subject.routine_parent, subject)

    def test_routine_only_subject_change_page_hides_mark_fields(self):
        user = get_user_model().objects.create_superuser(
            username='routine-subject-admin',
            email='routine-subject-admin@example.com',
            password='test-password',
        )
        subject = Subject.objects.create(
            subject_name='Agricultural Studies Practical',
            subject_code='134',
            subject_type='0',
            class_level='7',
            is_routine_only=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse('admin:myteacher_subject_change', args=[subject.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id_subject_name')
        self.assertContains(response, 'id_subject_code')
        self.assertNotContains(response, 'id_subject_type')
        self.assertNotContains(response, 'id_has_practical')
        self.assertNotContains(response, 'id_full_mark')
        self.assertNotContains(response, 'id_middle_routine_subject')
        self.assertNotContains(response, 'id_senior_routine_subject')

    def test_subject_add_page_places_routine_field_under_main_subject(self):
        user = get_user_model().objects.create_superuser(
            username='subject-add-admin',
            email='subject-add-admin@example.com',
            password='test-password',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('admin:myteacher_subject_add'))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertLess(content.index('id_subject_name'), content.index('id_middle_routine_subject'))
        self.assertLess(content.index('id_middle_routine_subject'), content.index('id_subject_code'))

    def test_all_group_creates_each_group_and_routine_only_practical_entries(self):
        form = self.save_subject_form(self.subject_form_data(
            '9',
            'ALL',
            senior_routine_subject='Physics Practical',
        ))

        self.assertTrue(form.create_all_groups)
        subjects = Subject.objects.order_by('group_name', 'is_routine_only')
        self.assertEqual(subjects.count(), 6)
        self.assertEqual(
            list(subjects.filter(is_routine_only=False).values_list('group_name', flat=True)),
            ['Arts', 'Commerce', 'Science'],
        )
        self.assertEqual(
            list(subjects.filter(is_routine_only=True).values_list('group_name', flat=True)),
            ['Arts', 'Commerce', 'Science'],
        )
        self.assertEqual(
            list(subjects.filter(is_routine_only=True).values_list('subject_code', flat=True)),
            ['136', '136', '136'],
        )

    def test_class_ten_add_page_offers_all_groups_and_saves_subject_for_each(self):
        user = get_user_model().objects.create_superuser(
            username='all-groups-admin',
            email='all-groups-admin@example.com',
            password='test-password',
        )
        self.client.force_login(user)

        add_page = self.client.get(reverse('admin:myteacher_subject_add'))
        self.assertEqual(add_page.status_code, 200)
        self.assertContains(add_page, 'All groups (Science, Arts, Commerce)')
        self.assertContains(add_page, 'subject_admin_form.js')

        response = self.client.post(
            reverse('admin:myteacher_subject_add'),
            self.subject_form_data(
                '10',
                'ALL',
                subject_name='Agricultural Studies',
                subject_code='134',
                subject_type='1',
            ),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            list(Subject.objects.filter(
                subject_name='Agricultural Studies',
                class_level='10',
                is_routine_only=False,
            ).order_by('group_name').values_list('group_name', flat=True)),
            ['Arts', 'Commerce', 'Science'],
        )

    def test_class_six_to_eight_combined_practical_is_routine_only(self):
        self.save_subject_form(self.subject_form_data(
            '6',
            middle_routine_subject='Science + Practical',
        ))

        practical = Subject.objects.get(subject_name='Science + Practical')
        self.assertTrue(practical.is_routine_only)
        self.assertEqual(practical.class_level, '6')
        self.assertEqual(practical.subject_code, '136')
        self.assertFalse(Subject.objects.filter(
            subject_name='Science + Practical',
            is_routine_only=False,
        ).exists())

    def test_all_groups_option_is_rejected_for_class_six_to_eight(self):
        form = SubjectAdminForm(data=self.subject_form_data('6', 'ALL'))

        self.assertFalse(form.is_valid())
        self.assertIn('group_name', form.errors)

    def test_routine_only_subjects_are_not_available_for_mark_entry(self):
        user = get_user_model().objects.create_user(
            username='routine-only-teacher',
            password='test-password',
        )
        teacher = Teacher.objects.create(
            user=user,
            teacher_id='RO001',
            teacher_name='Routine Only Teacher',
            designation='Assistant Teacher',
            mobile='01700000000',
            email='routine-only-teacher@example.com',
            assigned_class='6',
            teacher_img='',
        )
        regular_subject = Subject.objects.create(
            subject_name='Bangla',
            subject_type='1',
            class_level='6',
        )
        routine_subject = Subject.objects.create(
            subject_name='Bangla + Practical',
            subject_type='0',
            class_level='6',
            is_routine_only=True,
        )
        TeacherSubjectAssignment.objects.create(teacher=teacher, subject=regular_subject)
        TeacherSubjectAssignment.objects.create(teacher=teacher, subject=routine_subject)
        self.client.force_login(user)

        response = self.client.get(reverse('myteacher:mark_entry'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context['assignments'].values_list('subject__subject_name', flat=True)),
            ['Bangla'],
        )
        self.assertNotContains(response, 'Bangla + Practical')


class GroupSpecificSubjectTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username='group-subject-teacher',
            password='test-password',
        )
        self.teacher = Teacher.objects.create(
            user=user,
            teacher_id='GS001',
            teacher_name='Group Subject Teacher',
            designation='Assistant Teacher',
            mobile='01700000000',
            email='group-subject-teacher@example.com',
            assigned_class='9',
            teacher_img='',
        )
        self.user = user
        self.arts_student = self.create_student('7000001', 'Arts')
        self.commerce_student = self.create_student('7000002', 'Commerce')
        self.science_student = self.create_student('7000003', 'Science')
        self.arts_subject = self.create_subject('Arts Subject', 'Arts')
        self.general_subject = self.create_subject('General Subject')
        TeacherSubjectAssignment.objects.create(teacher=self.teacher, subject=self.arts_subject)
        TeacherSubjectAssignment.objects.create(teacher=self.teacher, subject=self.general_subject)

    def create_student(self, student_id, group):
        return Student.objects.create(
            photo='',
            full_name=f'{group} Student',
            father_name='Father',
            mother_name='Mother',
            student_id=student_id,
            gender='Male',
            date_of_birth='2008-01-01',
            current_class='9',
            class_roll=int(student_id[-1]),
            shift='Day',
            mobile_num='01700000000',
            group=group,
            religion='Islam',
        )

    def create_subject(self, subject_name, group_name=''):
        return Subject.objects.create(
            subject_name=subject_name,
            subject_type='1',
            religion='None',
            class_level='9',
            group_name=group_name,
        )

    def test_mark_entry_only_lists_and_saves_group_specific_students(self):
        self.client.force_login(self.user)
        url = reverse('myteacher:mark_entry')
        params = {
            'class_level': '9',
            'subject_id': self.arts_subject.id,
            'exam_type': 'Annual',
            'exam_year': '2026',
        }

        response = self.client.get(url, params)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['students']), [self.arts_student])
        self.assertContains(response, 'Only Arts students are shown')

        response = self.client.post(url, {
            **params,
            'subject_id': str(self.arts_subject.id),
            'class_level': '9',
            'exam_type': 'Annual',
            'exam_year': '2026',
            f'obj_{self.arts_student.id}': '20',
            f'obj_{self.commerce_student.id}': '80',
        })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Mark.objects.filter(student=self.arts_student, subject=self.arts_subject).exists())
        self.assertFalse(Mark.objects.filter(student=self.commerce_student, subject=self.arts_subject).exists())

    def test_general_subject_is_available_to_every_group(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('myteacher:mark_entry'), {
            'class_level': '9',
            'subject_id': self.general_subject.id,
            'exam_type': 'Annual',
            'exam_year': '2026',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.context['students']),
            {self.arts_student, self.commerce_student, self.science_student},
        )

    def test_other_group_subjects_are_excluded_from_result_cards_and_mark_validation(self):
        commerce_subject = self.create_subject('Commerce Subject', 'Commerce')
        marks = [
            Mark(
                mark_id=f'71000{index}',
                student=self.arts_student,
                subject=subject,
                exam_type='Annual',
                exam_year=2026,
                objective_mark=Decimal('20.00'),
            )
            for index, subject in enumerate(
                [self.arts_subject, commerce_subject, self.general_subject],
                start=1,
            )
        ]
        Mark.objects.bulk_create(marks)

        summary = get_student_result_summary(self.arts_student, 'Annual', 2026)
        result_subject_names = {row['subject_name'] for row in summary['marks']}
        result_card_subject_ids = set(self.arts_student.get_result_cards().values_list('subject_id', flat=True))

        self.assertEqual(result_subject_names, {'Arts Subject 1st', 'General Subject 1st'})
        self.assertEqual(result_card_subject_ids, {self.arts_subject.id, self.general_subject.id})
        with self.assertRaises(ValidationError):
            Mark.objects.create(
                student=self.arts_student,
                subject=commerce_subject,
                exam_type='Annual',
                exam_year=2026,
                objective_mark=Decimal('20.00'),
            )
