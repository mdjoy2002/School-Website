from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from myteacher.models import Mark, Subject
from myteacher.views import get_student_result_summary
from students.models import Student, StudentResultPublication


class ResultSummaryPublicationTests(TestCase):
    def test_unpublished_result_summary_hides_marks(self):
        student = Student.objects.create(
            photo=SimpleUploadedFile('student.jpg', b'img', content_type='image/jpeg'),
            full_name='Test Student',
            father_name='Father',
            mother_name='Mother',
            student_id='1234567',
            current_class='6',
            class_roll=1,
            mobile_num='01700000000',
            religion='Islam',
        )
        subject = Subject.objects.create(
            subject_name='Bangla',
            subject_code='BAN',
            subject_type='1',
            class_level='6',
            full_mark=Decimal('100.00'),
        )
        Mark.objects.create(
            student=student,
            subject=subject,
            exam_type='Annual',
            exam_year=2024,
            objective_mark=Decimal('70.00'),
            subjective_mark=Decimal('20.00'),
        )
        publication = StudentResultPublication.objects.create(
            class_level=student.current_class,
            exam_type='Annual',
            exam_year=2024,
            is_published=False,
        )

        summary = get_student_result_summary(student, 'Annual', '2024', publication=publication)

        self.assertEqual(summary['marks'], [])
        self.assertEqual(summary['subject_count'], 0)
        self.assertFalse(summary['has_marks'])
        self.assertEqual(summary['total_marks'], Decimal('0.00'))
        self.assertEqual(summary['overall_grade'], '-')
