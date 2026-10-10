import mimetypes
import os
import logging
import smtplib
import unicodedata

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.conf import settings
from django.core.validators import validate_email
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from PIL import Image, UnidentifiedImageError
from .admission_pdf import (
    admission_pdf_download_filename,
    ensure_admission_pdf,
    generate_admission_pdf,
)
from .models import (
    AdmissionSequence, Notice, Slider, EntryPopupImage, SchoolInfo, LeadershipProfile,
    CommitteeMember, Teacher, GalleryCategory,
    GalleryImage, ContactMessage, ExamRoutine, StudentCornerData,
    AdmissionInfo, AdmissionApplication, AdmissionApplySettings, ResultData
)

logger = logging.getLogger(__name__)


def _normalize_phone_number(value):
    return ''.join(
        str(unicodedata.decimal(character))
        for character in value
        if character.isdecimal()
    )


# হোম পেজের ভিউ
def home(request):
    # ১. নিউজ টিকারে (সর্বশেষ) দেখানোর জন্য সাধারণ নোটিশ + পরীক্ষার রুটিন (Ticker=True)
    ticker_notices = Notice.objects.filter(is_active=True, show_on_ticker=True).order_by('-created_at')
    ticker_routines = ExamRoutine.objects.filter(show_on_ticker=True).order_by('-created_at')
    
    # ২. হোমপেজ নোটিশ বোর্ডে সর্বোচ্চ ৭টি আইটেম দেখানো হবে যাতে বোর্ডে অতিরিক্ত ফাঁকা জায়গা না থাকে
    featured_notices = list(
        Notice.objects.filter(is_active=True, show_on_dashboard=True).order_by('-created_at')[:5]
    )
    featured_routines = list(
        ExamRoutine.objects.filter(show_on_notice=True).order_by('-created_at')[:2]
    )
    
    # নিউজ টিকারে হেডলাইন হিসেবে ব্যবহারের জন্য সাধারণ নোটিশ লিস্ট
    notices = Notice.objects.filter(is_active=True).order_by('-created_at')
    
    # হোমপেজে দেখানোর জন্য সর্বশেষ ৬টি গ্যালারি ইভেন্ট (শুধু যাদের কভার ইমেজ আছে)
    gallery_categories = GalleryCategory.objects.exclude(cover_image='').order_by('-created_at')[:6]
    
    # স্লাইডশোর জন্য একটিভ স্লাইডারগুলো নিয়ে আসা
    sliders = Slider.objects.filter(is_active=True).order_by('-created_at')

    # আমাদের সম্পর্কে (School Info) ডাটা নিয়ে আসা
    school_info = SchoolInfo.objects.first()

    leadership_profiles = LeadershipProfile.objects.in_bulk(field_name='profile_type')

    president_profile = leadership_profiles.get('PRESIDENT') or leadership_profiles.get('COMMITTEE')

    # হোমপেজে দেখানোর জন্য প্রথম ৪ জন শিক্ষক (স্লাইস ব্যবহার করা হয়েছে)
    teachers = Teacher.objects.all().order_by('order')[:4]

    context = {
        'ticker_notices': ticker_notices,
        'ticker_routines': ticker_routines,
        'featured_notices': featured_notices,
        'featured_routines': featured_routines,
        'notice_board_item_count': len(featured_notices) + len(featured_routines),
        'notices': notices,
        'gallery_categories': gallery_categories,
        'sliders': sliders,
        'school_info': school_info,

        'founder_profile': leadership_profiles.get('FOUNDER'),
        'headmaster_profile': leadership_profiles.get('HEADMASTER'),
        'president_profile': president_profile,
        'committee_profile': president_profile,

        'teachers': teachers,
        'entry_popup_images': [
            {'url': image.image.url, 'title': image.title}
            for image in EntryPopupImage.objects.filter(is_active=True).exclude(image='').order_by('order', 'pk')
        ],
    }
    
    return render(request, 'index.html', context)


# সকল নোটিশ টেবিল পেজের ভিউ (notices.html)
def all_notices_view(request):
    all_notices = Notice.objects.filter(is_active=True).order_by('-created_at')
    
    context = {
        'all_notices': all_notices,
    }
    
    return render(request, 'notices.html', context)


def notice_detail_view(request, notice_id):
    notice = get_object_or_404(Notice, id=notice_id, is_active=True)
    return render(request, 'notice_detail.html', {'notice': notice})


def notice_download_view(request, notice_id):
    notice = get_object_or_404(Notice, id=notice_id, is_active=True)
    return FileResponse(
        notice.file.open('rb'),
        as_attachment=True,
        filename=os.path.basename(notice.file.name),
    )


# পরীক্ষার রুটিন টেবিল পেজের ভিউ (exam_routine.html)
def exam_routine_view(request):
    routines = ExamRoutine.objects.all().order_by('-created_at')
    
    context = {
        'routines': routines,
    }
    
    return render(request, 'exam_routine.html', context)


# --- শিক্ষার্থী কর্নার ডাইনামিক ভিউ ---
def student_corner_detail(request, category_name):
    category_map = {
        'info': 'INFO',
        'seats': 'SEAT',
        'dress': 'DRESS',
        'class-routine': 'CLASS_ROUTINE',
        'syllabus': 'SYLLABUS',
        'exam-routine': 'EXAM_ROUTINE',
        'holiday': 'HOLIDAY',
    }
    
    titles = {
        'info': 'শ্রেণী ও লিঙ্গভিত্তিক শিক্ষার্থী তথ্য',
        'seats': 'শ্রেণী ভিত্তিক আসন সংখ্যা',
        'dress': 'স্কুল-কলেজের ড্রেস সম্পর্কিত তথ্য',
        'class-routine': 'ক্লাস রুটিন',
        'syllabus': 'সিলেবাস',
        'exam-routine': 'পরীক্ষার রুটিন',
        'holiday': 'ছুটির তালিকা',
    }
    
    db_category = category_map.get(category_name)
    if db_category == 'EXAM_ROUTINE':
        student_corner_items = list(StudentCornerData.objects.filter(category=db_category).order_by('-created_at'))
        exam_routine = list(ExamRoutine.objects.all().order_by('-created_at'))
        items = sorted(
            student_corner_items + exam_routine,
            key=lambda obj: obj.created_at,
            reverse=True
        )
    else:
        items = StudentCornerData.objects.filter(category=db_category).order_by('-created_at')
    
    context = {
        'items': items,
        'page_title': titles.get(category_name, 'শিক্ষার্থী কর্নার')
    }
    return render(request, 'student_corner_page.html', context)


# --- ভর্তি আবেদন ফর্ম ---
def admission_application_form(request):
    school_info = SchoolInfo.objects.first()
    admission_settings = AdmissionApplySettings.objects.filter(is_active=True).first()
    if not admission_settings:
        return render(request, 'admission_application_closed.html', {'school_info': school_info})

    def render_form(form_values=None):
        class_fees = {
            admission_class: str(admission_settings.fee_for_class(admission_class))
            for admission_class, _ in AdmissionApplication.ADMISSION_CLASS_CHOICES
        }
        return render(request, 'admission_application_form.html', {
            'school_info': school_info,
            'admission_settings': admission_settings,
            'class_fees': class_fees,
            'form_values': form_values or {},
            'document_options': {
                admission_class: admission_settings.documents_for_class(admission_class)
                for admission_class, _ in AdmissionApplication.ADMISSION_CLASS_CHOICES
            },
            'selected_documents': (
                form_values.getlist('submitted_documents')
                if hasattr(form_values, 'getlist') else []
            ),
        })

    if request.method == 'POST':
        allowed_fields = (
            'email', 'student_name_bn', 'student_name_en', 'date_of_birth', 'birth_reg_no', 'gender',
            'religion', 'blood_group', 'nationality', 'special_support_info', 'admission_class',
            'academic_year', 'section', 'roll_no', 'group', 'shift', 'admission_date',
            'admission_type', 'father_name', 'father_occupation', 'father_mobile', 'mother_name',
            'father_name_bn', 'father_name_en', 'mother_name_bn', 'mother_name_en',
            'mother_occupation', 'mother_mobile', 'guardian_name', 'guardian_relation',
            'guardian_mobile', 'parent_nid', 'emergency_contact', 'present_address',
            'permanent_address', 'village', 'post_office', 'upazila', 'district', 'postcode',
            'previous_school_name', 'previous_school_address', 'last_study_class',
            'last_exam_result', 'previous_roll', 'board_exam_info', 'tc_reference',
            'payment_reference',
        )
        form_data = {key: request.POST.get(key, '').strip() for key in allowed_fields}
        selected_document_values = set(request.POST.getlist('submitted_documents'))
        form_data['attached_documents'] = []
        form_data['same_as_permanent'] = 'হ্যাঁ' if request.POST.get('same_as_permanent') else 'না'
        raw_year = form_data['academic_year'].translate(str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789'))
        try:
            academic_year = int(raw_year)
        except ValueError:
            academic_year = None
        try:
            validate_email(form_data['email'])
        except ValidationError:
            messages.error(request, 'একটি সঠিক ইমেইল ঠিকানা দিন।')
            return render_form(request.POST)
        if (
            form_data['admission_class'] not in dict(AdmissionApplication.ADMISSION_CLASS_CHOICES)
            or not academic_year
            or academic_year < 1900
            or academic_year > 9999
            or len(raw_year) != 4
        ):
            messages.error(request, 'ভর্তির শ্রেণি এবং চার অঙ্কের শিক্ষাবর্ষ নির্বাচন করুন।')
            return render_form(request.POST)

        payment_methods = {
            'bkash': ('বিকাশ', 'bkash_enabled'),
            'nagad': ('নগদ', 'nagad_enabled'),
            'in_school': ('স্কুলে সরাসরি', 'in_school_enabled'),
        }
        selected_payment = request.POST.get('payment_method', '')
        if (
            selected_payment not in payment_methods
            or not getattr(admission_settings, payment_methods[selected_payment][1])
        ):
            messages.error(request, 'অনুগ্রহ করে চালু থাকা একটি বৈধ পেমেন্ট মাধ্যম নির্বাচন করুন।')
            return render_form(request.POST)
        preview_fee = admission_settings.fee_for_class(form_data['admission_class'])
        if preview_fee > 0 and selected_payment in ('bkash', 'nagad') and not form_data['payment_reference']:
            messages.error(request, 'বিকাশ/নগদ পেমেন্টের Transaction ID / রেফারেন্স নম্বর দিন।')
            return render_form(request.POST)

        uploaded_photo = request.FILES.get('student_photo')
        if not all(form_data[key] for key in (
            'student_name_bn', 'student_name_en', 'date_of_birth', 'birth_reg_no', 'gender', 'nationality',
            'father_name_bn', 'father_name_en', 'mother_name_bn', 'mother_name_en',
        )) or not uploaded_photo:
            messages.error(request, 'শিক্ষার্থী ও পিতা-মাতার আবশ্যক তথ্য পূরণ করে শিক্ষার্থীর ছবি আপলোড করুন।')
            return render_form(request.POST)
        if uploaded_photo.size > 300 * 1024:
            messages.error(request, 'শিক্ষার্থীর ছবির আকার ৩০০ KB-এর মধ্যে হতে হবে।')
            return render_form(request.POST)
        guardian_phone = _normalize_phone_number(form_data['guardian_mobile'])
        if not 7 <= len(guardian_phone) <= 15:
            messages.error(request, 'Application ID তৈরির জন্য অভিভাবকের সঠিক মোবাইল নম্বর দিন।')
            return render_form(request.POST)
        try:
            image = Image.open(uploaded_photo)
            image.verify()
        except (UnidentifiedImageError, OSError):
            messages.error(request, 'শিক্ষার্থীর ছবির জন্য একটি বৈধ image file আপলোড করুন।')
            return render_form(request.POST)
        uploaded_photo.seek(0)

        class_code = f"{6 + [name for name, _ in AdmissionApplication.ADMISSION_CLASS_CHOICES].index(form_data['admission_class']):02d}"
        try:
            with transaction.atomic():
                admission_settings = AdmissionApplySettings.objects.select_for_update().get(
                    pk=1, is_active=True
                )
                if not getattr(admission_settings, payment_methods[selected_payment][1]):
                    messages.error(request, 'অনুগ্রহ করে চালু থাকা একটি বৈধ পেমেন্ট মাধ্যম নির্বাচন করুন।')
                    return render_form(request.POST)

                fee = admission_settings.fee_for_class(form_data['admission_class'])
                form_data['attached_documents'] = [
                    document for document in admission_settings.documents_for_class(form_data['admission_class'])
                    if document in selected_document_values
                ]
                if fee > 0 and selected_payment in ('bkash', 'nagad') and not form_data['payment_reference']:
                    messages.error(request, 'বিকাশ/নগদ পেমেন্টের Transaction ID / রেফারেন্স নম্বর দিন।')
                    return render_form(request.POST)

                sequence, _ = AdmissionSequence.objects.get_or_create(
                    admission_class=form_data['admission_class'],
                    academic_year=academic_year,
                )
                application_number = sequence.next_application_number
                class_roll = sequence.next_roll_number
                application_id = (
                    f'KNU-{guardian_phone}-{academic_year}-{class_code}-{application_number:04d}'
                )
                form_data.update({
                    'application_id': application_id,
                    'class_roll_number': str(class_roll).zfill(2),
                    'payment_method': selected_payment,
                    'payment_method_display': payment_methods[selected_payment][0],
                    'application_fee': str(fee),
                    'payment_status': 'অপেক্ষমাণ' if fee > 0 else 'মওকুফ',
                    'admission_status': 'অপেক্ষমাণ',
                    'assigned_class': form_data['admission_class'],
                    'assigned_roll': str(class_roll).zfill(2),
                })
                application = AdmissionApplication.objects.create(
                    application_id=application_id,
                    email=form_data['email'],
                    admission_class=form_data['admission_class'],
                    academic_year=academic_year,
                    class_roll_number=class_roll,
                    application_fee=fee,
                    payment_status='PENDING' if fee > 0 else 'WAIVED',
                    assigned_class=form_data['admission_class'],
                    assigned_roll=class_roll,
                    application_data=form_data,
                    student_photo=uploaded_photo,
                )
                sequence.next_application_number += 1
                sequence.next_roll_number += 1
                sequence.save(update_fields=['next_application_number', 'next_roll_number'])
        except AdmissionApplySettings.DoesNotExist:
            return render(request, 'admission_application_closed.html', {'school_info': school_info})

        generate_admission_pdf(application)
        request.session['admission_application_id'] = application.pk
        status_url = request.build_absolute_uri(reverse('admission_status_lookup'))
        email_body = (
            f"আপনার ভর্তি আবেদন গ্রহণ করা হয়েছে।\n"
            f"Application ID: {application.application_id}\n"
            f"শ্রেণিভিত্তিক রোল: {class_roll:02d}\n"
            f"আবেদনের অবস্থা: অপেক্ষমাণ\n"
            f"আবেদনের অবস্থা দেখতে: {status_url}\n"
        )
        try:
            send_mail(
                subject=f'ভর্তি আবেদন গ্রহণ — {application.application_id}',
                message=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[application.email],
                fail_silently=False,
            )
            messages.success(
                request,
                f'আবেদন জমা হয়েছে। আপনার Application ID: {application.application_id}। নিশ্চিতকরণ ইমেইল পাঠানো হয়েছে।',
            )
        except (smtplib.SMTPException, OSError, RuntimeError):
            logger.exception('Admission confirmation email could not be sent for %s', application.application_id)
            messages.warning(
                request,
                f'আবেদন জমা হয়েছে। আপনার Application ID: {application.application_id}। ইমেইল পাঠানো যায়নি; এই ID সংরক্ষণ করুন।',
            )
        return redirect('admission_application_print')

    return render_form()


def admission_status_lookup(request):
    application = None
    searched = False
    if request.method == 'POST':
        searched = True
        application_id = request.POST.get('application_id', '').strip()
        email = request.POST.get('email', '').strip()
        if application_id and email:
            application = AdmissionApplication.objects.filter(
                application_id__iexact=application_id,
                email__iexact=email,
            ).first()
        if application:
            request.session['admission_status_application_id'] = application.pk
        else:
            request.session.pop('admission_status_application_id', None)
    return render(request, 'admission_application_status.html', {
        'application': application,
        'searched': searched,
    })


def admission_status_pdf(request):
    application_id = request.session.get('admission_status_application_id')
    if not application_id:
        raise Http404
    application = get_object_or_404(AdmissionApplication, pk=application_id)
    ensure_admission_pdf(application)
    download = request.GET.get('download') == '1'
    response = FileResponse(
        application.pdf_file.open('rb'),
        as_attachment=download,
        filename=admission_pdf_download_filename(application),
        content_type='application/pdf',
    )
    response['X-Content-Type-Options'] = 'nosniff'
    return response


# --- ভর্তি আবেদন ফরম প্রিভিউ/প্রিন্ট ---
def admission_application_print(request):
    application_id = request.session.get('admission_application_id')
    application = get_object_or_404(AdmissionApplication, pk=application_id) if application_id else None
    form_data = dict(application.application_data) if application else {}
    if application:
        attached_documents = form_data.get('attached_documents', [])
        if isinstance(attached_documents, str):
            attached_documents = [item.strip() for item in attached_documents.split(',') if item.strip()]
        form_data['attached_documents'] = attached_documents
        form_data.update({
            'email': application.email,
            'application_id': application.application_id,
            'class_roll_number': f'{application.class_roll_number:02d}' if application.class_roll_number else '',
            'admission_status': application.get_status_display(),
            'payment_status': application.get_payment_status_display(),
            'assigned_class': application.get_assigned_class_display() or '',
            'assigned_section': application.get_assigned_section_display() or '',
            'assigned_roll': f'{application.assigned_roll:02d}' if application.assigned_roll else '',
            'approver_name': application.approver_name,
            'approval_date': application.admission_confirmed_at.strftime('%d-%m-%Y') if application.admission_confirmed_at else '',
            'office_comment': application.office_comment,
        })
    else_data = {
        'school_name_bangla': 'খন্দকার নাসের উদ্দিন মাধ্যমিক বিদ্যালয়',
        'school_name_english': 'Khondakar Naser Uddin Secondary School',
        'school_code': 'KNS-001',
        'address': 'বয়রা, খুলনা, বাংলাদেশ',
    }
    school_info = SchoolInfo.objects.first()
    if school_info:
        else_data.update({
            'school_name_bangla': school_info.school_name_bangla or else_data['school_name_bangla'],
            'school_name_english': school_info.school_name_english or else_data['school_name_english'],
            'school_code': school_info.school_code or else_data['school_code'],
            'address': school_info.address or else_data['address'],
        })
    merged_data = {**else_data, **form_data}
    context = {
        'form_data': merged_data,
        'school_info': school_info,
        'application': application,
    }
    return render(request, 'admission_application_print.html', context)


def admission_application_download_pdf(request):
    application_id = request.session.get('admission_application_id')
    if not application_id:
        raise Http404
    application = get_object_or_404(AdmissionApplication, pk=application_id)
    ensure_admission_pdf(application)
    return FileResponse(
        application.pdf_file.open('rb'),
        as_attachment=True,
        filename=admission_pdf_download_filename(application),
    )


def admission_application_student_photo(request):
    application_id = request.session.get('admission_application_id')
    if not application_id:
        raise Http404
    application = get_object_or_404(AdmissionApplication, pk=application_id)
    if (
        not application.student_photo
        or not application.student_photo.storage.exists(application.student_photo.name)
    ):
        raise Http404
    content_type = mimetypes.guess_type(application.student_photo.name)[0] or 'application/octet-stream'
    return FileResponse(application.student_photo.open('rb'), content_type=content_type)


# --- ভর্তি তথ্য ডাইনামিক ভিউ ---
def admission_detail(request, category):
    titles = {
        'form': 'ভর্তি আবেদন ফরম',
        'guide': 'ভর্তি নির্দেশিকা',
        'result': 'ভর্তি পরীক্ষার ফলাফল',
        'fees': 'বেতন ও ফি সমূহ',
    }
    
    admission_data = AdmissionInfo.objects.filter(category=category).order_by('-created_at')
    
    context = {
        'items': admission_data,
        'page_title': titles.get(category, 'ভর্তি তথ্য')
    }
    return render(request, 'admission_detail.html', context)


# --- নতুন সংযোজন: ফলাফল ডাইনামিক ভিউ ---
def result_category_view(request, category):
    titles = {
        'public': 'পাবলিক পরীক্ষার ফলাফল',
        'internal': 'স্কুল ও কলেজের ফলাফল',
    }
    
    items = ResultData.objects.filter(category=category).order_by('-created_at')
    
    context = {
        'items': items,
        'page_title': titles.get(category, 'ফলাফল')
    }
    return render(request, 'result_detail.html', context)


# শিক্ষক ও কর্মচারীবৃন্দের জন্য আলাদা পেজের ভিউ
def teachers_view(request):
    if request.method == 'POST':
        if not request.user.is_authenticated or not (request.user.is_staff or request.user.is_superuser):
            messages.error(request, "আপনার অনুমতি নেই। লগইন করে পুনরায় চেষ্টা করুন।")
            return redirect('teachers_page')

        teacher_id = request.POST.get('teacher_id')
        teacher = get_object_or_404(Teacher, id=teacher_id)
        teacher.subject = request.POST.get('subject', '').strip()
        selected_designation = request.POST.get('designation')
        allowed_designations = {
            'HEAD': ['Headmaster'],
            'TEACHER': ['Senior Teacher', 'Assistant Teacher'],
            'STAFF': ['Night Guard', 'Cleaner', 'Aya'],
        }.get(teacher.teacher_type, [])
        if selected_designation in allowed_designations:
            teacher.designation = selected_designation
        teacher.save()
        messages.success(request, "শিক্ষক তথ্য সফলভাবে হালনাগাদ করা হয়েছে।")
        return redirect('teachers_page')

    teachers = Teacher.objects.all().order_by('order')
    designation_options_by_type = {
        'HEAD': [('Headmaster', 'প্রতিষ্ঠান প্রধান')],
        'TEACHER': [
            ('Senior Teacher', 'সিনিয়র শিক্ষক'),
            ('Assistant Teacher', 'সহকারী শিক্ষক'),
        ],
        'STAFF': [
            ('Kormochari', 'কর্মচারী'),
        ],
    }
    
    context = {
        'teachers': teachers,
        'designation_options_by_type': designation_options_by_type,
        'can_edit_teachers': request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser),
    }
    
    return render(request, 'teachers.html', context)


def committee_view(request):
    members_by_category = [
        {
            'value': category_value,
            'name': category_label,
            'members': CommitteeMember.objects.filter(category=category_value),
        }
        for category_value, category_label in CommitteeMember.CATEGORY_CHOICES
    ]
    return render(request, 'committee.html', {'members_by_category': members_by_category})


# গ্যালারি পেজের জন্য ভিউ (যেখানে সব ফোল্ডার/ইভেন্ট দেখা যাবে)
def gallery_view(request):
    # শুধুমাত্র সেই ক্যাটাগরিগুলো নিন যেগুলোতে ছবি আছে
    categories = GalleryCategory.objects.exclude(cover_image='').prefetch_related('images').order_by('-created_at')
    
    context = {
        'categories': categories,
    }
    
    return render(request, 'gallery.html', context)


# যোগাযোগ পেজের জন্য ভিউ (অভিযোগ সেভ করার লজিকসহ)
def contact_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        subject = request.POST.get('subject')
        message_text = request.POST.get('message')

        ContactMessage.objects.create(
            name=name,
            phone=phone,
            subject=subject,
            message=message_text
        )
        
        messages.success(request, "আপনার অভিযোগ বা বার্তাটি সফলভাবে জমা হয়েছে। ধন্যবাদ!")
        
        return redirect('contact')

    school_info = SchoolInfo.objects.first()
    
    context = {
        'school_info': school_info,
    }
    
    return render(request, 'contact.html', context)