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
        self.assertEqual(third_summary['position'], 3)
        self.assertEqual(third_summary['position_display'], '3rd')

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
