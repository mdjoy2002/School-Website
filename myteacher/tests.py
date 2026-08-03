from decimal import Decimal
from types import SimpleNamespace

from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.contrib.auth import get_user_model

from myteacher.models import Mark, Subject, Teacher, TeacherSubjectAssignment
from myteacher.views import get_student_result_summary, mark_entry_view
from students.models import Student, StudentResultPublication


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

    def test_optional_subject_failure_does_not_render_as_failing_row(self):
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

        self.assertNotIn('<tr class="failing-row">', html)

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
        self.assertEqual(third_summary['position'], 3)
        self.assertEqual(third_summary['position_display'], '3rd')

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
