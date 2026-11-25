from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from myteacher.models import ExamRoutine, Subject

from .models import Student, StudentAdmitCardSetting, StudentPromotionHistory


class StudentBloodGroupAdminTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin_user = User.objects.create_superuser(
            username='blood-group-admin',
            email='blood-group-admin@example.com',
            password='test-password',
        )
        self.student = Student.objects.create(
            photo='',
            full_name='Existing Student',
            father_name='Father',
            mother_name='Mother',
            student_id='S10003',
            gender='Male',
            current_class='6',
            class_roll=3,
            shift='Day',
            mobile_num='01700000003',
            blood_group='',
        )
        self.client.force_login(self.admin_user)

    def test_existing_student_blood_group_is_editable_from_admin_list(self):
        url = reverse('admin:students_student_changelist')
        response = self.client.get(url)

        self.assertContains(response, 'name="form-0-blood_group"')
        response = self.client.post(url, {
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '1',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-id': str(self.student.pk),
            'form-0-blood_group': 'O+',
            '_save': 'Save',
        })

        self.student.refresh_from_db()
        self.assertEqual(self.student.blood_group, 'O+')


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

    def test_student_id_is_generated_when_blank_and_is_unique(self):
        student_data = {
            'photo': '',
            'full_name': 'New Student',
            'father_name': 'Father',
            'mother_name': 'Mother',
            'student_id': '',
            'current_class': '6',
            'class_roll': 2,
            'mobile_num': '01700000002',
            'login_enabled': False,
        }

        first_student = Student.objects.create(**student_data)
        second_student = Student.objects.create(**{**student_data, 'class_roll': 3})

        self.assertRegex(first_student.student_id, r'^\d{7}$')
        self.assertRegex(second_student.student_id, r'^\d{7}$')
        self.assertNotEqual(first_student.student_id, second_student.student_id)

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

    def test_admit_card_routines_only_include_students_religious_subject(self):
        for subject_name, religion, subject_code, subject_type in (
            ('Islamic Studies', 'Islam', 'IS101', '0'),
            ('Hindu Religious Studies', 'Hindu', 'HR101', '0'),
            ('English', 'None', 'E101', '1'),
            ('English', 'None', 'E102', '2'),
            ('Optional Subject', 'None', 'O401', '4'),
        ):
            Subject.objects.create(
                subject_name=subject_name,
                subject_code=subject_code,
                subject_type=subject_type,
                religion=religion,
                class_level='6',
            )
            ExamRoutine.objects.create(
                class_name='6',
                group_name='',
                exam_type='Half Yearly',
                exam_year=2026,
                subject_name=subject_name,
                subject_code=subject_code,
                exam_date='2026-10-11',
            )

        hindu_student = Student.objects.create(
            photo='',
            full_name='Hindu Student',
            father_name='Father',
            mother_name='Mother',
            student_id='S10002',
            gender='Female',
            date_of_birth='2010-01-01',
            current_class='6',
            class_roll=2,
            shift='Day',
            mobile_num='01700000002',
            religion='Hindu',
        )

        muslim_subjects = {
            routine.display_subject_name for routine in self.student.get_routines()
        }
        hindu_subjects = {
            routine.display_subject_name for routine in hindu_student.get_routines()
        }
        expected_common_subjects = {
            'English 1st',
            'English 2nd',
            'Optional Subject (4th Subject)',
        }

        self.assertEqual(
            muslim_subjects,
            expected_common_subjects | {'Islamic Studies'},
        )
        self.assertEqual(
            hindu_subjects,
            expected_common_subjects | {'Hindu Religious Studies'},
        )
