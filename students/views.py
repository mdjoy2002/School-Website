from itertools import groupby

from django.apps import apps
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.db import models
from django.shortcuts import redirect, render

from .models import Student, StudentPromotionHistory, StudentTicker, StudentResultPublication
from django.shortcuts import get_object_or_404
from django.http import HttpResponseForbidden
from myteacher.views import get_student_result_summary, is_head_or_admin


def student_home(request):
    return render(request, 'student_home.html', {'student': getattr(request.user, 'student_profile', None)})


def student_login(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        # Try to find Student by Student ID first, then authenticate using the linked User
        student = None
        try:
            student = Student.objects.get(student_id=username)
        except Student.DoesNotExist:
            student = None

        user = None
        if student and student.user:
            user = authenticate(request, username=student.user.username, password=password)
        else:
            # Fallback to normal authenticate if no matching student or no linked user
            user = authenticate(request, username=username, password=password)

        if user is not None and hasattr(user, 'student_profile'):
            login(request, user)
            messages.success(request, 'Student portal access granted.')
            return redirect('student_profile', student_id=user.student_profile.student_id)

        messages.error(request, 'Invalid Student ID or password. Please try again.')

    return render(request, 'student_login.html')


def student_logout(request):
    logout(request)
    return redirect('student_login')


def student_dashboard(request):
    if not request.user.is_authenticated:
        return redirect('student_login')

    student = getattr(request.user, 'student_profile', None)
    if not student:
        logout(request)
        return redirect('student_login')

    Mark = apps.get_model('myteacher', 'Mark')
    marks = Mark.objects.filter(student=student).select_related('subject').order_by('-exam_year', 'exam_type', 'subject__subject_name')

    grouped_results = []
    for (class_level, exam_type, exam_year), group in groupby(
        marks,
        key=lambda m: (getattr(m.subject, 'class_level', None) or student.current_class, m.exam_type, m.exam_year),
    ):
        grouped_results.append({
            'class_level': class_level,
            'exam_type': exam_type,
            'exam_year': exam_year,
            'marks': list(group),
            'is_current_class': class_level == student.current_class,
        })

    admit_cards = student.get_admit_cards()
    promotions = StudentPromotionHistory.objects.filter(student=student).order_by('-promoted_at')

    return render(request, 'student_dashboard.html', {
        'student': student,
        'result_cards': grouped_results,
        'admit_cards': admit_cards,
        'promotions': promotions,
    })


def student_credentials_view(request):
    if not request.user.is_authenticated:
        messages.error(request, 'Please login first.')
        return redirect('student_login')

    allowed = False
    # superuser or staff
    if request.user.is_superuser or request.user.is_staff:
        allowed = True
    # allow headmaster / assistant headmaster teacher users
    elif hasattr(request.user, 'teacher') and is_head_or_admin(request.user.teacher, request.user):
        allowed = True

    if not allowed:
        messages.error(request, 'Only headmaster or admin can access this page.')
        return redirect('student_login')

    class_groups = []
    for class_level in ['6', '7', '8', '9', '10']:
        students = Student.objects.filter(current_class=class_level).order_by('class_roll', 'full_name')
        if students.exists():
            class_groups.append((class_level, students))

    return render(request, 'student_credentials.html', {'class_groups': class_groups})


def student_profile(request, student_id):
    student = get_object_or_404(Student, student_id=student_id)
    user = request.user
    allowed = False
    can_view_sensitive = False
    if user.is_authenticated:
        # Allow only the student themself or superuser to view full profile
        if user.is_superuser:
            allowed = True
            can_view_sensitive = True
        elif hasattr(user, 'student_profile') and user.student_profile == student:
            allowed = True
            can_view_sensitive = True

    if not allowed:
        return HttpResponseForbidden("You are not authorized to view this student's profile.")

    # Prev / Next navigation within the same class (by class_roll)
    class_students = list(Student.objects.filter(current_class=student.current_class).order_by('class_roll').values_list('student_id', flat=True))
    prev_student_id = None
    next_student_id = None
    try:
        idx = class_students.index(student.student_id)
        if idx > 0:
            prev_student_id = class_students[idx - 1]
        if idx < len(class_students) - 1:
            next_student_id = class_students[idx + 1]
    except ValueError:
        prev_student_id = None
        next_student_id = None

    # Result cards grouping (reuse logic from dashboard)
    Mark = apps.get_model('myteacher', 'Mark')
    marks = Mark.objects.filter(student=student).select_related('subject').order_by('-exam_year', 'exam_type', 'subject__subject_name')

    grouped_results = []
    for (class_level, exam_type, exam_year), group in groupby(
        marks,
        key=lambda m: (getattr(m.subject, 'class_level', None) or student.current_class, m.exam_type, m.exam_year),
    ):
        grouped_results.append({
            'class_level': class_level,
            'exam_type': exam_type,
            'exam_year': exam_year,
            'marks': list(group),
            'is_current_class': class_level == student.current_class,
        })

    if request.method == 'POST':
        if not user.is_authenticated or not hasattr(user, 'student_profile') or user.student_profile != student:
            return HttpResponseForbidden("You can only update your own profile.")

        mobile_num = request.POST.get('mobile_num', '').strip()
        if mobile_num:
            student.mobile_num = mobile_num
            student.save(update_fields=['mobile_num'])
            messages.success(request, 'Your phone number has been updated successfully.')
            return redirect('student_profile', student_id=student.student_id)
        else:
            messages.error(request, 'Please enter a valid phone number.')

    admit_cards = student.get_admit_cards()

    student_tickers = StudentTicker.objects.filter(is_active=True).filter(
        models.Q(show_to_all=True) | models.Q(target_students=student)
    ).distinct()

    # Build available exam options from this student's marks
    exam_options = []
    seen_exams = set()
    for group in grouped_results:
        option_key = (group['exam_type'], group['exam_year'])
        if option_key not in seen_exams:
            seen_exams.add(option_key)
            exam_options.append({
                'exam_type': group['exam_type'],
                'exam_year': group['exam_year'],
                'label': f"{group['exam_type']} {group['exam_year']}",
            })

    # Determine selected exam from query parameters or default to latest available
    selected_exam = request.GET.get('exam_type')
    selected_year = request.GET.get('exam_year')
    selected_option = request.GET.get('exam_option')
    if selected_option:
        parts = selected_option.split('||')
        if len(parts) == 2:
            selected_exam, selected_year = parts[0], parts[1]

    if not selected_exam or not selected_year:
        MarkModel = apps.get_model('myteacher', 'Mark')
        latest_mark = MarkModel.objects.filter(student=student).order_by('-exam_year').values('exam_type', 'exam_year').first()
        if latest_mark:
            selected_exam = latest_mark.get('exam_type')
            selected_year = str(latest_mark.get('exam_year'))
    else:
        selected_year = str(selected_year)

    result_summary = None
    result_published = None
    if selected_exam and selected_year:
        publication = StudentResultPublication.objects.filter(
            class_level=student.current_class,
            exam_type=selected_exam,
            exam_year=selected_year
        ).first()
        result_published = publication.is_published if publication else False
        if result_published:
            result_summary = get_student_result_summary(student, selected_exam, selected_year)

    return render(request, 'student_profile.html', {
        'student': student,
        'can_view_sensitive': can_view_sensitive,
        'prev_student_id': prev_student_id,
        'next_student_id': next_student_id,
        'result_cards': grouped_results,
        'admit_cards': admit_cards,
        'student_tickers': student_tickers,
        'result_data': result_summary,
        'selected_exam': selected_exam,
        'selected_year': selected_year,
        'exam_options': exam_options,
        'result_published': result_published,
    })