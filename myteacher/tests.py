from decimal import Decimal

from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.uploadedfile import SimpleUploadedFile
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
