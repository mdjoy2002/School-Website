from django.shortcuts import render, redirect
from django.contrib import messages
from .models import (
    Notice, Slider, SchoolInfo, Teacher, GalleryCategory, 
    GalleryImage, ContactMessage, ExamRoutine, StudentCornerData,
    AdmissionInfo, ResultData # নতুন মডেল ইমপোর্ট করা হয়েছে
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
    
    # হোমপেজে দেখানোর জন্য সর্বশেষ ৬টি গ্যালারি ইভেন্ট/ফোল্ডার নিয়ে আসা
    gallery_categories = GalleryCategory.objects.all().order_by('-created_at')[:6]
    
    # স্যালটি স্লাইডশোর জন্য একটিভ স্লাইডারগুলো নিয়ে আসা
    sliders = Slider.objects.filter(is_active=True).order_by('-created_at')

    # আমাদের সম্পর্কে (School Info) ডাটা নিয়ে আসা
    school_info = SchoolInfo.objects.first()
    
    # হোমপেজে দেখানোর জন্য প্রথম ৪ জন শিক্ষক (স্লাইস ব্যবহার করা হয়েছে)
    teachers = Teacher.objects.all().order_by('order')[:4]
    
    context = {
        'ticker_notices': ticker_notices,
        'ticker_routines': ticker_routines, # টিকারে রুটিন দেখানোর জন্য
        'featured_notices': featured_notices,
        'featured_routines': featured_routines, # নোটিশ বোর্ডে রুটিন দেখানোর জন্য
        'notices': notices,
        'gallery_categories': gallery_categories,
        'sliders': sliders,
        'school_info': school_info,
        'teachers': teachers,
    }
    
    return render(request, 'index.html', context)


# সকল নোটিশ টেবিল পেজের ভিউ (notices.html)
def all_notices_view(request):
    # সকল একটিভ নোটিশ প্রকাশের তারিখ অনুযায়ী সিরিয়াল করে নিয়ে আসা
    all_notices = Notice.objects.filter(is_active=True).order_by('-created_at')
    
    context = {
        'all_notices': all_notices,
    }
    
    return render(request, 'notices.html', context)


# পরীক্ষার রুটিন টেবিল পেজের ভিউ (exam_routine.html)
def exam_routine_view(request):
    # সকল ক্লাসের পরীক্ষার রুটিন সর্বশেষ আপলোড অনুযায়ী নিয়ে আসা
    routines = ExamRoutine.objects.all().order_by('-created_at')
    
    context = {
        'routines': routines,
    }
    
    return render(request, 'exam_routine.html', context)


# --- শিক্ষার্থী কর্নার ডাইনামিক ভিউ ---
def student_corner_detail(request, category_name):
    # ইউআরএল থেকে আসা ক্যাটাগরি অনুযায়ী ডাটা ম্যাপ করা
    category_map = {
        'info': 'INFO',
        'seats': 'SEAT',
        'dress': 'DRESS',
        'class-routine': 'CLASS_ROUTINE',
        'syllabus': 'SYLLABUS',
        'holiday': 'HOLIDAY',
    }
    
    # টাইটেল ম্যাপ করা
    titles = {
        'info': 'শ্রেণী ও লিঙ্গভিত্তিক শিক্ষার্থী তথ্য',
        'seats': 'শ্রেণী ভিত্তিক আসন সংখ্যা',
        'dress': 'স্কুল-কলেজের ড্রেস সম্পর্কিত তথ্য',
        'class-routine': 'ক্লাস রুটিন',
        'syllabus': 'সিলেবাস',
        'holiday': 'ছুটির তালিকা',
    }
    
    db_category = category_map.get(category_name)
    # আপনার টেমপ্লেটের লুপের সাথে মিল রাখার জন্য data_list বদলে items করা হয়েছে
    items = StudentCornerData.objects.filter(category=db_category).order_by('-created_at')
    
    context = {
        'items': items,
        'page_title': titles.get(category_name, 'শিক্ষার্থী কর্নার')
    }
    return render(request, 'student_corner_page.html', context)


# --- ভর্তি তথ্য ডাইনামিক ভিউ ---
def admission_detail(request, category):
    # ক্যাটাগরি অনুযায়ী টাইটেল ম্যাপ করা
    titles = {
        'form': 'ভর্তি আবেদন ফরম',
        'guide': 'ভর্তি নির্দেশিকা',
        'result': 'ভর্তি পরীক্ষার ফলাফল',
        'fees': 'বেতন ও ফি সমূহ',
    }
    
    # ডাটা ফিল্টার করা
    admission_data = AdmissionInfo.objects.filter(category=category).order_by('-created_at')
    
    context = {
        'items': admission_data,
        'page_title': titles.get(category, 'ভর্তি তথ্য')
    }
    return render(request, 'admission_detail.html', context)


# --- নতুন সংযোজন: ফলাফল ডাইনামিক ভিউ ---
def result_category_view(request, category):
    # ক্যাটাগরি অনুযায়ী টাইটেল ম্যাপ করা
    titles = {
        'public': 'পাবলিক পরীক্ষার ফলাফল',
        'internal': 'স্কুল ও কলেজের ফলাফল',
    }
    
    # ডাটা ফিল্টার করা (টেমপ্লেটের লুপের জন্য results বদলে items করা হয়েছে)
    items = ResultData.objects.filter(category=category).order_by('-created_at')
    
    context = {
        'items': items,
        'page_title': titles.get(category, 'ফলাফল')
    }
    return render(request, 'result_detail.html', context)


# শিক্ষক ও কর্মচারীবৃন্দের জন্য আলাদা পেজের ভিউ
def teachers_view(request):
    # সকল শিক্ষক ও কর্মচারীদের ডাটা সিরিয়াল অনুযায়ী নিয়ে আসা
    teachers = Teacher.objects.all().order_by('order')
    
    context = {
        'teachers': teachers,
    }
    
    return render(request, 'teachers.html', context)


# গ্যালারি পেজের জন্য ভিউ (যেখানে সব ফোল্ডার/ইভেন্ট দেখা যাবে)
def gallery_view(request):
    # সকল ইভেন্ট এবং তাদের ভেতরে থাকা ছবিগুলো প্রি-ফেচ করে নিয়ে আসা
    categories = GalleryCategory.objects.all().prefetch_related('images').order_by('-created_at')
    
    context = {
        'categories': categories,
    }
    
    return render(request, 'gallery.html', context)


# যোগাযোগ পেজের জন্য ভিউ (অভিযোগ সেভ করার লজিকসহ)
def contact_view(request):
    if request.method == 'POST':
        # ফর্ম থেকে ডাটা সংগ্রহ
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        subject = request.POST.get('subject')
        message_text = request.POST.get('message')

        # ডাটাবেসে অভিযোগ সেভ করা
        ContactMessage.objects.create(
            name=name,
            phone=phone,
            subject=subject,
            message=message_text
        )
        
        # সফলতার মেসেজ সেট করা
        messages.success(request, "আপনার অভিযোগ বা বার্তাটি সফলভাবে জমা হয়েছে। ধন্যবাদ!")
        
        # পুনরায় কন্টাক্ট পেজেই রিডাইরেক্ট করা
        return redirect('contact')

    # GET রিকোয়েস্টের জন্য স্কুলের তথ্যসহ পেজ রেন্ডার করা
    school_info = SchoolInfo.objects.first()
    
    context = {
        'school_info': school_info,
    }
    
    return render(request, 'contact.html', context)