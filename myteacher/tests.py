from decimal import Decimal
from types import SimpleNamespace

from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from myteacher.admin import ExamRoutineAdminForm
from myteacher.models import ExamRoutine, Mark, Subject, Teacher, TeacherSubjectAssignment
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

        response = self.client.get(reverse('myteacher:manage_routine'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'value="{subject.pk}"')
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
