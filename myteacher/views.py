from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from .models import Student, TeacherSubjectAssignment, Mark, Subject, ExamRoutine, TeacherClassAssignment, Teacher
from django.http import HttpResponse, HttpResponseForbidden
from django.template.loader import get_template
from django.urls import reverse
from django.db.models import Q
from decimal import Decimal, InvalidOperation
from io import BytesIO
from xhtml2pdf import pisa
import datetime


def calculate_grade_and_gpa(score):
    try:
        score = float(score)
    except (TypeError, ValueError):
        return '-', '0.00'

    if score >= 80:
        return 'A+', '5.00'
    if score >= 70:
        return 'A', '4.00'
    if score >= 60:
        return 'A-', '3.50'
    if score >= 50:
        return 'B', '3.00'
    if score >= 40:
        return 'C', '2.00'
    if score >= 33:
        return 'D', '1.00'
    return 'F', '0.00'


@login_required
def home(request):
    # শিক্ষক লগইন করা থাকলে তাকে ড্যাশবোর্ডে পাঠান
    return redirect('myteacher:dashboard') 
@login_required
def teacher_profile(request):
    teacher = request.user.teacher
    return render(request, 'myteacher/profile.html', {'teacher': teacher})

@login_required
def dashboard_view(request):
    teacher = request.user.teacher
    
    # Get all assignments for this teacher
    assignments = TeacherSubjectAssignment.objects.filter(teacher=teacher)
    
    # Get all classes assigned to this teacher
    assigned_classes = TeacherClassAssignment.objects.filter(teacher=teacher).values_list('class_level', flat=True)
    
    # Get students from all assigned classes
    class_students = None
    if assigned_classes:
        class_students = Student.objects.filter(current_class__in=assigned_classes).order_by('current_class', 'class_roll')
    elif teacher.is_class_teacher and teacher.class_teacher_of:
        # Fallback to old system if teacher is class teacher
        class_students = Student.objects.filter(current_class=teacher.class_teacher_of).order_by('class_roll')
        
    return render(request, 'myteacher/dashboard.html', {
        'teacher': teacher,
        'assignments': assignments,
        'class_students': class_students,
        'assigned_classes': list(assigned_classes),
        'can_manage_routine': teacher.is_class_teacher or is_head_or_admin(teacher, request.user),
    })

@login_required
def mark_entry_view(request):
    teacher = request.user.teacher
    assignments = TeacherSubjectAssignment.objects.filter(teacher=teacher)
    
    # Get assigned classes for this teacher
    assigned_classes = TeacherClassAssignment.objects.filter(teacher=teacher).values_list('class_level', flat=True)
    
    selected_class = request.GET.get('class_level')
    selected_subject = request.GET.get('subject_id')
    selected_exam = request.GET.get('exam_type')
    selected_year = request.GET.get('exam_year') or str(datetime.date.today().year)
    exam_years = [str(year) for year in range(datetime.date.today().year - 3, datetime.date.today().year + 2)]
    
    students = None
    selected_subject_obj = None
    
    # Validate selected class is assigned to teacher
    if selected_class and selected_class not in assigned_classes:
        return HttpResponseForbidden("You are not authorized to access this class.")

    if selected_class and selected_subject and selected_exam and selected_year:
        assignment = assignments.filter(subject_id=selected_subject, subject__class_level=selected_class).first()
        if not assignment:
            return HttpResponseForbidden("You are not authorized to enter marks for this subject/class.")

        selected_subject_obj = assignment.subject
        students = Student.objects.filter(current_class=selected_class).order_by('class_roll')
        subject_full_mark = selected_subject_obj.full_mark_value
        
        for student in students:
            student.mark = Mark.objects.filter(
                student=student, 
                subject=selected_subject_obj,
                exam_type=selected_exam,
                exam_year=selected_year,
            ).first()
            if student.mark:
                student.total_mark = student.mark.total_mark
                percentage = (student.total_mark / subject_full_mark * Decimal('100.00')) if subject_full_mark else Decimal('0.00')
                student.grade, student.gpa = calculate_grade_and_gpa(percentage)
            else:
                student.total_mark = Decimal('0.00')
                student.grade, student.gpa = calculate_grade_and_gpa(0)

    if request.method == 'POST':
        subject_id = request.POST.get('subject_id')
        s_class = request.POST.get('class_level')
        exam_type = request.POST.get('exam_type')
        exam_year = request.POST.get('exam_year') or str(datetime.date.today().year)
        
        # Validate class is assigned to teacher
        if s_class not in assigned_classes:
            return HttpResponseForbidden("Unauthorized access!")
        
        if not assignments.filter(subject_id=subject_id, subject__class_level=s_class).exists():
            return HttpResponseForbidden("Unauthorized access!")

        students_to_mark = Student.objects.filter(current_class=s_class)
        
        for student in students_to_mark:
            obj = request.POST.get(f'obj_{student.id}', 0) or 0
            sub = request.POST.get(f'sub_{student.id}', 0) or 0
            ct = request.POST.get(f'ct_{student.id}', 0) or 0
            prac = request.POST.get(f'prac_{student.id}', 0) or 0

            try:
                obj = Decimal(obj)
            except (TypeError, ValueError, InvalidOperation):
                obj = Decimal('0.00')
            try:
                sub = Decimal(sub)
            except (TypeError, ValueError, InvalidOperation):
                sub = Decimal('0.00')
            try:
                ct = Decimal(ct)
            except (TypeError, ValueError, InvalidOperation):
                ct = Decimal('0.00')
            try:
                prac = Decimal(prac)
            except (TypeError, ValueError, InvalidOperation):
                prac = Decimal('0.00')

            Mark.objects.update_or_create(
                student=student,
                subject_id=subject_id,
                exam_type=exam_type,
                exam_year=exam_year,
                defaults={
                    'objective_mark': obj,
                    'subjective_mark': sub,
                    'class_test_mark': ct,
                    'practical_mark': prac,
                    'exam_year': exam_year,
                }
            )
        # রিডাইরেক্টের সময় প্যারামিটারগুলো সাথে পাঠানো হচ্ছে
        url = reverse('myteacher:mark_entry')
        return redirect(f"{url}?class_level={s_class}&subject_id={subject_id}&exam_type={exam_type}&exam_year={exam_year}")

    return render(request, 'myteacher/mark_entry.html', {
        'assignments': assignments,
        'assigned_classes': list(assigned_classes),
        'selected_class': selected_class,
        'selected_subject': selected_subject,
        'selected_exam': selected_exam,
        'selected_year': selected_year,
        'exam_years': exam_years,
        'selected_subject_obj': selected_subject_obj,
        'students': students
    })

@login_required
def mark_entry_history_view(request):
    teacher = request.user.teacher
    assignments = TeacherSubjectAssignment.objects.filter(teacher=teacher)
    assigned_classes = TeacherClassAssignment.objects.filter(teacher=teacher).values_list('class_level', flat=True)

    selected_class = request.GET.get('class_level')
    selected_subject = request.GET.get('subject_id')
    selected_exam = request.GET.get('exam_type')

    marks = Mark.objects.none()
    selected_subject_obj = None

    if selected_class:
        if selected_class not in assigned_classes:
            return HttpResponseForbidden("You are not authorized to access this class.")

        marks = Mark.objects.filter(student__current_class=selected_class)

        if selected_subject:
            selected_subject_obj = get_object_or_404(Subject, id=selected_subject)
            marks = marks.filter(subject=selected_subject_obj)

        if selected_exam:
            marks = marks.filter(exam_type=selected_exam)

        marks = marks.select_related('student', 'subject').order_by('student__class_roll')

    return render(request, 'myteacher/mark_entry_history.html', {
        'assignments': assignments,
        'assigned_classes': list(assigned_classes),
        'selected_class': selected_class,
        'selected_subject': selected_subject,
        'selected_exam': selected_exam,
        'selected_subject_obj': selected_subject_obj,
        'marks': marks,
    })

# mark show view and print button

# testimonial template view

# class update view 


def manage_routine_view(request):
    teacher = request.user.teacher
    is_head_teacher = is_head_or_admin(teacher, request.user)

    # Only class teachers and head/admin may manage routines
    if not teacher.is_class_teacher and not is_head_teacher:
        return HttpResponseForbidden("আপনি রুটিন তৈরি বা সম্পাদনা করার অনুমোদিত নন।")

    if is_head_teacher:
        routines = ExamRoutine.objects.all().order_by('exam_date', 'class_name')
    else:
        routines = ExamRoutine.objects.filter(class_name=teacher.class_teacher_of).order_by('exam_date', 'class_name')

    edit_mode = False
    routine_id = ''
    class_name = ''
    group_name = ''
    exam_type = 'Half Yearly'
    exam_year = datetime.date.today().year
    subject = ''
    subject_code = ''
    date = ''
    time = '10:00 AM'
    selected_apply_to = []
    selected_bulk_groups = []

    if request.method == 'POST':
        if 'save_routine' in request.POST:
            hidden_id = request.POST.get('routine_id')
            c = request.POST.get('class_name')
            g = request.POST.get('group_name') if c in ['9', '10'] else ''
            
            # Validate only class teacher or head/admin may save routines
            if not is_head_teacher and c != teacher.class_teacher_of:
                return HttpResponseForbidden("আপনি এই ক্লাসের জন্য রুটিন তৈরি বা সম্পাদনা করার অনুমোদিত নন।")
            
            et = request.POST.get('exam_type')
            ey = request.POST.get('exam_year') or datetime.date.today().year
            s = request.POST.get('subject')
            sc = request.POST.get('subject_code')
            d = request.POST.get('date')
            t = request.POST.get('time')
            extra_classes = request.POST.getlist('apply_to')
            bulk_groups = request.POST.getlist('bulk_groups')

            if hidden_id:
                routine = get_object_or_404(ExamRoutine, id=hidden_id)
                routine.class_name = c
                routine.group_name = g
                routine.exam_type = et
                routine.exam_year = ey
                routine.subject_name = s
                routine.subject_code = sc
                routine.exam_date = d
                routine.exam_time = t
                routine.save()
            else:
                routine = ExamRoutine.objects.create(
                    class_name=c,
                    group_name=g,
                    exam_type=et,
                    exam_year=ey,
                    subject_name=s,
                    subject_code=sc,
                    exam_date=d,
                    exam_time=t
                )
                for ec in extra_classes:
                    if ec != c:
                        if ec in ['9', '10'] and bulk_groups:
                            for bg in bulk_groups:
                                ExamRoutine.objects.create(
                                    class_name=ec,
                                    group_name=bg,
                                    exam_type=routine.exam_type,
                                    exam_year=routine.exam_year,
                                    subject_name=routine.subject_name,
                                    subject_code=routine.subject_code,
                                    exam_date=routine.exam_date,
                                    exam_time=routine.exam_time
                                )
                        else:
                            ExamRoutine.objects.create(
                                class_name=ec,
                                group_name='' if ec not in ['9', '10'] else g,
                                exam_type=routine.exam_type,
                                exam_year=routine.exam_year,
                                subject_name=routine.subject_name,
                                subject_code=routine.subject_code,
                                exam_date=routine.exam_date,
                                exam_time=routine.exam_time
                            )
            return redirect('myteacher:manage_routine')

        elif 'clear_all' in request.POST:
            ExamRoutine.objects.all().delete()
            return redirect('myteacher:manage_routine')

    if request.method == 'GET' and 'edit' in request.GET:
        edit_mode = True
        routine_id = request.GET.get('edit')
        routine = get_object_or_404(ExamRoutine, id=routine_id)
        class_name = routine.class_name
        group_name = routine.group_name or ''
        exam_type = routine.exam_type
        exam_year = routine.exam_year
        subject = routine.subject_name
        subject_code = routine.subject_code
        date = routine.exam_date.strftime('%Y-%m-%d')
        time = routine.exam_time

    return render(request, 'myteacher/manage_routine.html', {
        'routines': routines,
        'edit_mode': edit_mode,
        'routine_id': routine_id,
        'class_name': class_name,
        'group_name': group_name,
        'exam_type': exam_type,
        'exam_year': exam_year,
        'subject': subject,
        'subject_code': subject_code,
        'date': date,
        'time': time,
        'selected_apply_to': selected_apply_to,
        'selected_bulk_groups': selected_bulk_groups,
    })

# ডিলিট এবং কপি ভিউ
def delete_routine(request, id):
    teacher = request.user.teacher
    is_head_teacher = is_head_or_admin(teacher, request.user)
    if not teacher.is_class_teacher and not is_head_teacher:
        return HttpResponseForbidden("আপনি রুটিন মুছে ফেলার অনুমোদিত নন।")

    routine = get_object_or_404(ExamRoutine, id=id)
    if not is_head_teacher and routine.class_name != teacher.class_teacher_of:
        return HttpResponseForbidden("আপনি এই রুটিনটি মুছে ফেলার অনুমোদিত নন।")

    routine.delete()
    return redirect('myteacher:manage_routine')

def copy_routine(request, from_id, target_class):
    teacher = request.user.teacher
    is_head_teacher = is_head_or_admin(teacher, request.user)
    if not teacher.is_class_teacher and not is_head_teacher:
        return HttpResponseForbidden("আপনি রুটিন কপি করার অনুমোদিত নন।")

    original = get_object_or_404(ExamRoutine, id=from_id)
    if not is_head_teacher and original.class_name != teacher.class_teacher_of:
        return HttpResponseForbidden("আপনি এই রুটিনটি কপি করার অনুমোদিত নন।")

    original.pk = None  # নতুন অবজেক্ট তৈরির জন্য
    original.class_name = target_class
    original.group_name = original.group_name if target_class in ['9', '10'] else ''
    original.save()
    return redirect('myteacher:manage_routine')

@login_required
def view_routine(request):
    years = ExamRoutine.objects.order_by('-exam_year').values_list('exam_year', flat=True).distinct()
    selected_year = request.GET.get('year')
    selected_type = request.GET.get('type', '')

    if not selected_year:
        selected_year = years[0] if years else datetime.date.today().year

    exam_types = ExamRoutine.objects.filter(exam_type__isnull=False).exclude(exam_type='').values_list('exam_type', flat=True).distinct()

    routines = ExamRoutine.objects.filter(exam_year=selected_year)
    if selected_type:
        routines = routines.filter(exam_type=selected_type)

    dates = routines.order_by('exam_date').values_list('exam_date', flat=True).distinct()

    date_rows = []
    for exam_date in dates:
        row = {'date': exam_date, 'cells': []}

        def find_routine(class_name, group_name=''):
            try:
                return routines.get(class_name=class_name, group_name=group_name, exam_date=exam_date)
            except ExamRoutine.DoesNotExist:
                return None

        for class_val in ['6', '7', '8']:
            routine = find_routine(class_val)
            row['cells'].append(routine)

        for group_val in ['Science', 'Commerce', 'Arts']:
            row['cells'].append(find_routine('9', group_val))
        for group_val in ['Science', 'Commerce', 'Arts']:
            row['cells'].append(find_routine('10', group_val))

        date_rows.append(row)

    return render(request, 'myteacher/view_routine.html', {
        'years': years,
        'exam_types': exam_types,
        'selected_year': selected_year,
        'selected_type': selected_type,
        'date_rows': date_rows,
        'now_year': datetime.date.today().year,
    })


@login_required
def student_corner_view(request):
    teacher = request.user.teacher
    is_head_teacher = is_head_or_admin(teacher, request.user)
    class_teacher_classes = get_teacher_class_teacher_classes(teacher)
    
    if is_head_teacher:
        assigned_classes = list(Student.objects.order_by('current_class').values_list('current_class', flat=True).distinct())
    else:
        assigned_classes = get_teacher_allowed_classes(teacher)
        if not assigned_classes and class_teacher_classes:
            assigned_classes = class_teacher_classes
    
    selected_class = request.GET.get('class_level')
    search_query = request.GET.get('search', '').strip()

    students = Student.objects.none()
    class_students = None
    
    if assigned_classes:
        if selected_class and selected_class in assigned_classes:
            current_class = selected_class
        else:
            current_class = assigned_classes[0]
        
        class_students = Student.objects.filter(current_class=current_class).order_by('class_roll')
        if search_query:
            class_students = class_students.filter(
                Q(full_name__icontains=search_query) |
                Q(student_id__icontains=search_query) |
                Q(father_name__icontains=search_query) |
                Q(mother_name__icontains=search_query)
            )
        
        students = class_students
        selected_class = current_class

    return render(request, 'myteacher/student_corner.html', {
        'teacher': teacher,
        'assigned_classes': assigned_classes,
        'selected_class': selected_class,
        'class_students': class_students,
        'students': students,
        'search_query': search_query,
        'can_generate_admit': bool(class_teacher_classes) or is_head_teacher,
        'can_generate_seat': bool(class_teacher_classes) or is_head_teacher,
        'is_head_teacher': is_head_teacher,
    })


@login_required
def id_cards_view(request):
    teacher = request.user.teacher
    is_head_teacher = is_head_or_admin(teacher, request.user)
    class_teacher_classes = get_teacher_class_teacher_classes(teacher)
    viewable_classes = get_teacher_viewable_classes(teacher, request.user)

    selected_class = request.GET.get('class_level')
    if selected_class and selected_class not in viewable_classes:
        selected_class = None

    if not selected_class:
        if class_teacher_classes:
            selected_class = class_teacher_classes[0]
        elif viewable_classes:
            selected_class = viewable_classes[0]

    students = Student.objects.none()
    if selected_class:
        students = Student.objects.filter(current_class=selected_class).order_by('class_roll')

    can_download = selected_class in class_teacher_classes or is_head_teacher
    current_year = datetime.date.today().year

    return render(request, 'myteacher/id_cards.html', {
        'teacher': teacher,
        'assigned_classes': viewable_classes,
        'selected_class': selected_class,
        'students': students,
        'can_download': can_download,
        'current_year': current_year,
        'is_head_teacher': is_head_teacher,
    })


@login_required
def seat_plan_view(request):
    teacher = request.user.teacher
    assigned_class = teacher.class_teacher_of if teacher.is_class_teacher else None
    students = Student.objects.filter(current_class=assigned_class).order_by('class_roll') if assigned_class else None
    return render(request, 'myteacher/seat_plan.html', {
        'teacher': teacher,
        'assigned_class': assigned_class,
        'students': students,
    })


def is_head_or_admin(teacher, user):
    return user.is_superuser or teacher.designation in ['Headmaster', 'Assistant Headmaster']


def get_teacher_allowed_classes(teacher):
    return list(TeacherClassAssignment.objects.filter(teacher=teacher).values_list('class_level', flat=True))


def get_teacher_class_teacher_classes(teacher):
    assigned_classes = list(TeacherClassAssignment.objects.filter(teacher=teacher).values_list('class_level', flat=True))
    if not assigned_classes and teacher.is_class_teacher and teacher.class_teacher_of:
        assigned_classes = [teacher.class_teacher_of]
    return assigned_classes


def get_teacher_viewable_classes(teacher, user):
    if is_head_or_admin(teacher, user):
        return list(Student.objects.order_by('current_class').values_list('current_class', flat=True).distinct())

    allowed_classes = get_teacher_allowed_classes(teacher)
    class_teacher_classes = get_teacher_class_teacher_classes(teacher)
    if class_teacher_classes:
        for c in class_teacher_classes:
            if c not in allowed_classes:
                allowed_classes.append(c)
    return allowed_classes


def get_student_result_summary(student, exam_type, exam_year=None):
    marks = Mark.objects.filter(student=student, exam_type=exam_type).select_related('subject').order_by('subject__subject_name')
    if exam_year is not None:
        try:
            exam_year = int(exam_year)
            marks = marks.filter(exam_year=exam_year)
        except (TypeError, ValueError):
            pass
    subject_results = []
    total_marks = Decimal('0.00')
    total_possible_marks = Decimal('0.00')
    total_gpa = Decimal('0.00')
    subject_count = 0
    fail_count = 0

    # Group Bangla/English papers into one combined subject grade
    grouped_marks = {}
    for mark in marks:
        lower_name = mark.subject.subject_name.strip().lower()
        is_combined_subject = (
            mark.subject.subject_type in ['1', '2'] and
            ('bangla' in lower_name or 'english' in lower_name)
        )
        if is_combined_subject:
            grouped_marks.setdefault(lower_name, []).append(mark)
        else:
            obtained = mark.total_mark
            subject_max = mark.subject.full_mark_value
            percentage = (obtained / subject_max * Decimal('100.00')) if subject_max else Decimal('0.00')
            grade, gpa = calculate_grade_and_gpa(percentage)
            subject_type = mark.subject.subject_type
            subject_type_label = None
            if subject_type == '1':
                subject_type_label = '1st'
            elif subject_type == '2':
                subject_type_label = '2nd'
            subject_name = mark.subject.subject_name
            if subject_type_label:
                subject_name = f"{subject_name} {subject_type_label}"

            subject_results.append({
                'subject_name': subject_name,
                'subject_type': mark.subject.get_subject_type_display() if hasattr(mark.subject, 'get_subject_type_display') else mark.subject.subject_type,
                'objective_mark': mark.objective_mark,
                'subjective_mark': mark.subjective_mark,
                'class_test_mark': mark.class_test_mark,
                'practical_mark': mark.practical_mark or Decimal('0.00'),
                'total_mark': obtained,
                'full_mark': subject_max,
                'grade': grade,
                'gpa': gpa,
                'group_rowspan': 1,
                'show_combined': True,
            })
            total_marks += obtained
            total_possible_marks += subject_max
            total_gpa += Decimal(gpa)
            subject_count += 1
            if grade == 'F':
                fail_count += 1

    for lower_name, grouped in grouped_marks.items():
        if len(grouped) > 1:
            grouped.sort(key=lambda m: m.subject.subject_type)
            combined_full_mark = sum(m.subject.full_mark_value for m in grouped)
            combined_total_mark = sum(m.total_mark for m in grouped)
            combined_percentage = (combined_total_mark / combined_full_mark * Decimal('100.00')) if combined_full_mark else Decimal('0.00')
            combined_grade, combined_gpa = calculate_grade_and_gpa(combined_percentage)

            for index, mark in enumerate(grouped):
                subject_type_label = '1st' if mark.subject.subject_type == '1' else '2nd' if mark.subject.subject_type == '2' else ''
                subject_name = mark.subject.subject_name
                if subject_type_label:
                    subject_name = f"{subject_name} {subject_type_label}"

                row = {
                    'subject_name': subject_name,
                    'subject_type': mark.subject.get_subject_type_display() if hasattr(mark.subject, 'get_subject_type_display') else mark.subject.subject_type,
                    'objective_mark': mark.objective_mark,
                    'subjective_mark': mark.subjective_mark,
                    'class_test_mark': mark.class_test_mark,
                    'practical_mark': mark.practical_mark or Decimal('0.00'),
                    'total_mark': mark.total_mark,
                    'full_mark': mark.subject.full_mark_value,
                    'group_rowspan': len(grouped),
                    'show_combined': index == 0,
                }

                if index == 0:
                    row.update({
                        'combined_total_mark': combined_total_mark,
                        'combined_gpa': combined_gpa,
                        'combined_grade': combined_grade,
                        'combined_percentage': combined_percentage.quantize(Decimal('0.00')),
                        'gpa': combined_gpa,
                        'grade': combined_grade,
                    })
                    total_gpa += Decimal(combined_gpa)
                    subject_count += 1
                    if combined_grade == 'F':
                        fail_count += 1
                subject_results.append(row)
                total_marks += mark.total_mark
                total_possible_marks += mark.subject.full_mark_value
        else:
            mark = grouped[0]
            obtained = mark.total_mark
            subject_max = mark.subject.full_mark_value
            percentage = (obtained / subject_max * Decimal('100.00')) if subject_max else Decimal('0.00')
            grade, gpa = calculate_grade_and_gpa(percentage)
            subject_type = mark.subject.subject_type
            subject_type_label = None
            if subject_type == '1':
                subject_type_label = '1st'
            elif subject_type == '2':
                subject_type_label = '2nd'
            subject_name = mark.subject.subject_name
            if subject_type_label:
                subject_name = f"{subject_name} {subject_type_label}"

            subject_results.append({
                'subject_name': subject_name,
                'subject_type': mark.subject.get_subject_type_display() if hasattr(mark.subject, 'get_subject_type_display') else mark.subject.subject_type,
                'objective_mark': mark.objective_mark,
                'subjective_mark': mark.subjective_mark,
                'class_test_mark': mark.class_test_mark,
                'practical_mark': mark.practical_mark or Decimal('0.00'),
                'total_mark': obtained,
                'full_mark': subject_max,
                'grade': grade,
                'gpa': gpa,
                'group_rowspan': 1,
                'show_combined': True,
                'combined_total_mark': obtained,
                'combined_gpa': gpa,
                'combined_grade': grade,
                'combined_percentage': percentage.quantize(Decimal('0.00')),
            })
            total_marks += obtained
            total_possible_marks += subject_max
            total_gpa += Decimal(gpa)
            subject_count += 1
            if grade == 'F':
                fail_count += 1

    subject_results.sort(key=lambda entry: (
        0 if entry['subject_name'].lower().startswith('bangla 1st') else
        1 if entry['subject_name'].lower().startswith('bangla 2nd') else
        2 if entry['subject_name'].lower().startswith('english 1st') else
        3 if entry['subject_name'].lower().startswith('english 2nd') else
        10,
        entry['subject_name'].lower()
    ))

    if subject_count > 0 and total_possible_marks > 0:
        average_mark = total_marks / subject_count
        overall_percentage = (total_marks / total_possible_marks * Decimal('100.00'))
        overall_grade, overall_gpa = calculate_grade_and_gpa(overall_percentage)
        average_gpa = (total_gpa / subject_count).quantize(Decimal('0.00'))
        result_status = 'Pass' if fail_count == 0 else 'Fail'
    else:
        average_mark = Decimal('0.00')
        average_gpa = Decimal('0.00')
        overall_grade = '-'
        overall_gpa = '0.00'
        overall_percentage = Decimal('0.00')
        result_status = 'Incomplete'

    return {
        'student': student,
        'marks': subject_results,
        'subject_count': subject_count,
        'total_marks': total_marks,
        'total_possible_marks': total_possible_marks,
        'percentage': overall_percentage.quantize(Decimal('0.00')) if subject_count and total_possible_marks > 0 else Decimal('0.00'),
        'average_mark': average_mark.quantize(Decimal('0.00')) if subject_count else average_mark,
        'average_gpa': average_gpa,
        'overall_gpa': overall_gpa,
        'overall_grade': overall_grade,
        'result_status': result_status,
        'has_marks': subject_count > 0,
    }


def render_to_pdf(template_src, context_dict):
    template = get_template(template_src)
    html = template.render(context_dict)
    result = BytesIO()
    pdf_status = pisa.CreatePDF(html, dest=result)
    if pdf_status.err:
        return None
    return result.getvalue()


@login_required
def student_results_view(request):
    teacher = request.user.teacher
    exam_choices = [choice[0] for choice in Mark.EXAM_CHOICES]
    all_classes = list(Student.objects.order_by('current_class').values_list('current_class', flat=True).distinct())

    selected_class = request.GET.get('class_level') or (all_classes[0] if all_classes else None)
    selected_exam = request.GET.get('exam_type') or (exam_choices[0] if exam_choices else None)
    exam_years = [str(year) for year in Mark.objects.order_by('-exam_year').values_list('exam_year', flat=True).distinct()]
    if not exam_years:
        exam_years = [str(datetime.date.today().year)]
    selected_year = request.GET.get('exam_year') or str(datetime.date.today().year)
    search_query = request.GET.get('search', '').strip()
    student_pk = request.GET.get('student_id', '').strip()

    class_students = Student.objects.none()
    student_summary = None
    class_summary = []

    if selected_class:
        class_students = Student.objects.filter(current_class=selected_class).order_by('class_roll')
        if search_query:
            class_students = class_students.filter(
                Q(full_name__icontains=search_query) |
                Q(student_id__icontains=search_query)
            )

        for student in class_students:
            summary = get_student_result_summary(student, selected_exam, selected_year)
            class_summary.append(summary)

        if student_pk and student_pk.isdigit():
            selected_student = get_object_or_404(Student, id=int(student_pk), current_class=selected_class)
            student_summary = get_student_result_summary(selected_student, selected_exam, selected_year)

    return render(request, 'myteacher/student_results.html', {
        'teacher': teacher,
        'allowed_classes': all_classes,
        'class_levels': all_classes,
        'exam_choices': exam_choices,
        'exam_years': exam_years,
        'selected_class': selected_class,
        'selected_exam': selected_exam,
        'selected_year': selected_year,
        'search_query': search_query,
        'class_students': class_students,
        'result_data': student_summary,
        'class_summary': class_summary,
    })

    if selected_class:
        class_students = Student.objects.filter(current_class=selected_class).order_by('class_roll')
        if search_query:
            class_students = class_students.filter(
                Q(full_name__icontains=search_query) |
                Q(student_id__icontains=search_query)
            )

        for student in class_students:
            summary = get_student_result_summary(student, selected_exam, selected_year)
            class_summary.append(summary)

        if student_pk and student_pk.isdigit():
            selected_student = get_object_or_404(Student, id=int(student_pk), current_class=selected_class)
            student_summary = get_student_result_summary(selected_student, selected_exam, selected_year)

    return render(request, 'myteacher/student_results.html', {
        'teacher': teacher,
        'allowed_classes': allowed_classes,
        'exam_choices': exam_choices,
        'exam_years': exam_years,
        'selected_class': selected_class,
        'selected_exam': selected_exam,
        'selected_year': selected_year,
        'search_query': search_query,
        'class_students': class_students,
        'result_data': student_summary,
        'class_summary': class_summary,
    })


@login_required
def student_results_pdf_view(request, student_id):
    teacher = request.user.teacher
    selected_exam = request.GET.get('exam_type') or (Mark.EXAM_CHOICES[0][0] if Mark.EXAM_CHOICES else 'Half Yearly')
    selected_year = request.GET.get('exam_year') or str(datetime.date.today().year)
    student = get_object_or_404(Student, id=student_id)

    student_summary = get_student_result_summary(student, selected_exam, selected_year)
    context = {
        'results': [student_summary],
        'selected_exam': selected_exam,
        'exam_year': selected_year,
        'school_name': 'খন্দকার নাসের উদ্দীন মাধ্যমিক বিদ্যালয়',
        'generated_on': datetime.date.today(),
    }
    pdf = render_to_pdf('myteacher/student_result_pdf.html', context)
    if not pdf:
        return HttpResponse("PDF generation failed. Please try again.")
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="result_{student.student_id}_{selected_exam}.pdf"'
    return response


@login_required
def generate_admit_card(request):
    if request.method == 'POST':
        teacher = request.user.teacher
        class_teacher_classes = get_teacher_class_teacher_classes(teacher)
        is_head_teacher = is_head_or_admin(teacher, request.user)
        
        student_ids = request.POST.getlist('student_ids')
        exam_name = request.POST.get('exam_name') or 'Examination'
        exam_year = request.POST.get('exam_year') or datetime.date.today().year

        if not student_ids:
            student_ids = request.POST.getlist('student_ids[]')

        if not student_ids:
            return render(request, 'myteacher/error.html', {'message': 'অনুগ্রহ করে স্টুডেন্ট সিলেক্ট করুন!'})

        students = Student.objects.filter(id__in=student_ids)
        for student in students:
            if not is_head_teacher and student.current_class not in class_teacher_classes:
                return HttpResponseForbidden("You are not authorized to generate admit card for this student!")
        
        students = students.order_by('current_class', 'class_roll')
        context = {
            'students': students,
            'exam_title': f"{exam_name} - {exam_year}",
            'exam_year': exam_year,
            'selected_ids': student_ids,
        }
        return render(request, 'myteacher/admit_card_template.html', context)
    return render(request, 'myteacher/error.html', {'message': 'Invalid Request'})


@login_required
def generate_seat_plan(request):
    if request.method == 'POST':
        teacher = request.user.teacher
        class_teacher_classes = get_teacher_class_teacher_classes(teacher)
        is_head_teacher = is_head_or_admin(teacher, request.user)
        
        student_ids = request.POST.getlist('student_ids')
        exam_name = request.POST.get('exam_name')
        exam_year = request.POST.get('exam_year')

        if not student_ids:
            student_ids = request.POST.getlist('student_ids[]')

        if not student_ids:
            return render(request, 'myteacher/error.html', {'message': 'অনুগ্রহ করে স্টুডেন্ট সিলেক্ট করুন!'})

        # Validate that all students belong to assigned classes
        students = Student.objects.filter(id__in=student_ids)
        for student in students:
            if not is_head_teacher and student.current_class not in class_teacher_classes:
                return HttpResponseForbidden("You are not authorized to generate seat plan for this student!")
        
        students = students.order_by('current_class', 'class_roll')
        return render(request, 'myteacher/seat_plan_template.html', {
            'students': students,
            'exam_name': exam_name,
            'exam_year': exam_year,
            'logo_url': '/static/images/logo.png',
        })
    return render(request, 'myteacher/error.html', {'message': 'Invalid Request'})

# models.py-তে যোগ করুন
def get_routines(self):
    return ExamRoutine.objects.filter(class_name=self.current_class).order_by('exam_date')

@login_required
def student_list_view(request):
    teacher = request.user.teacher
    is_head_teacher = is_head_or_admin(teacher, request.user)
    class_filter = request.GET.get('class_filter', '')

    if is_head_teacher:
        students_qs = Student.objects.all()
    else:
        allowed_classes = get_teacher_allowed_classes(teacher)
        class_teacher_classes = get_teacher_class_teacher_classes(teacher)
        if class_teacher_classes:
            allowed_classes = list(set(allowed_classes) | set(class_teacher_classes))
        students_qs = Student.objects.filter(current_class__in=allowed_classes)

    if class_filter:
        students_qs = students_qs.filter(current_class=class_filter)

    students = students_qs.order_by('current_class', 'class_roll')
    class_teacher_classes = get_teacher_class_teacher_classes(teacher)
    return render(request, 'myteacher/student_list.html', {
        'students': students,
        'selected_class': class_filter,
        'is_head_teacher': is_head_teacher,
        'can_generate_admit': bool(class_teacher_classes) or is_head_teacher,
        'can_generate_seat': bool(class_teacher_classes) or is_head_teacher,
    })
