from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import Student, StudentAdmitCardSetting, StudentPromotionHistory


class StudentPortalTests(TestCase):
    def setUp(self):
        self.student = Student.objects.create(
            photo='',
            full_name='Rahim Ahmed',
            father_name='Kamal Ahmed',
            mother_name='Asha Ahmed',
            student_id='S10001',
            gender='Male',
            date_of_birth='2010-01-01',
            current_class='6',
            class_roll=1,
            shift='Day',
            mobile_num='01700000001',
            group='Science',
            religion='Islam',
        )

    def test_generate_login_credentials_creates_user_and_password(self):
        self.student.ensure_login_credentials()

        self.assertIsNotNone(self.student.user)
        self.assertEqual(self.student.user.username, self.student.student_id)
        self.assertTrue(self.student.user.check_password(self.student.generated_password))

    def test_promotion_records_history_for_previous_class(self):
        self.student.ensure_login_credentials()
        self.student.promote_to_next_class()

        history = StudentPromotionHistory.objects.filter(student=self.student).first()
        self.assertIsNotNone(history)
        self.assertEqual(history.from_class, '6')
        self.assertEqual(history.to_class, '7')
        self.assertEqual(self.student.current_class, '7')

    def test_admit_card_setting_can_be_enabled_for_exam(self):
        setting = StudentAdmitCardSetting.objects.create(
            class_level='6',
            exam_type='Half Yearly',
            exam_year=2026,
            is_enabled=True,
        )

        self.assertTrue(setting.is_enabled)
        self.assertEqual(setting.display_name, 'Class 6 • Half Yearly • 2026')
