from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import (
    Notice, Slider, SchoolInfo, Teacher, GalleryCategory, 
    GalleryImage, ContactMessage, ExamRoutine, StudentCornerData,
    AdmissionInfo, ResultData
)

# হোম পেজের ভিউ
def home(request):
    # ১. নিউজ টিকারে (সর্বশেষ) দেখানোর জন্য সাধারণ নোটিশ + পরীক্ষার রুটিন (Ticker=True)
    ticker_notices = Notice.objects.filter(is_active=True, show_on_ticker=True).order_by('-created_at')
    ticker_routines = ExamRoutine.objects.filter(show_on_ticker=True).order_by('-created_at')
    
    # ২. হোমপেজ নোটিশ বোর্ডে দেখানোর জন্য ডাটা (show_on_dashboard=True, সর্বোচ্চ ৬টি)
    featured_notices = Notice.objects.filter(is_active=True, show_on_dashboard=True).order_by('-created_at')[:6]
    featured_routines = ExamRoutine.objects.filter(show_on_notice=True).order_by('-created_at')[:4]
    
    # নিউজ টিকারে হেডলাইন হিসেবে ব্যবহারের জন্য সাধারণ নোটিশ লিস্ট
    notices = Notice.objects.filter(is_active=True).order_by('-created_at')
    
    # হোমপেজে দেখানোর জন্য সর্বশেষ ৬টি গ্যালারি ইভেন্ট (শুধু যাদের কভার ইমেজ আছে)
    gallery_categories = GalleryCategory.objects.exclude(cover_image='').order_by('-created_at')[:6]
    
    # স্লাইডশোর জন্য একটিভ স্লাইডারগুলো নিয়ে আসা
    sliders = Slider.objects.filter(is_active=True).order_by('-created_at')

    # আমাদের সম্পর্কে (School Info) ডাটা নিয়ে আসা
    school_info = SchoolInfo.objects.first()
    
    # হোমপেজে দেখানোর জন্য প্রথম ৪ জন শিক্ষক (স্লাইস ব্যবহার করা হয়েছে)
    teachers = Teacher.objects.all().order_by('order')[:4]
    
    context = {
        'ticker_notices': ticker_notices,
        'ticker_routines': ticker_routines, 
        'featured_notices': featured_notices,
        'featured_routines': featured_routines,
        'notices': notices,
        'gallery_categories': gallery_categories,
        'sliders': sliders,
        'school_info': school_info,
        'teachers': teachers,
    }
    
    return render(request, 'index.html', context)


# সকল নোটিশ টেবিল পেজের ভিউ (notices.html)
def all_notices_view(request):
    all_notices = Notice.objects.filter(is_active=True).order_by('-created_at')
    
    context = {
        'all_notices': all_notices,
    }
    
    return render(request, 'notices.html', context)


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