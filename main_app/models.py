from django.db import models

# ১. নোটিশ বোর্ড
class Notice(models.Model):
    title = models.CharField(max_length=200, verbose_name="নোটিশের শিরোনাম")
    description = models.TextField(verbose_name="বিস্তারিত", blank=True, null=True)
    file = models.FileField(upload_to='notices/', verbose_name="পিডিএফ ফাইল (PDF)")
    
    show_on_ticker = models.BooleanField(default=False, verbose_name="নিউজ টিকারে (সর্বশেষ) দেখাবে?")
    show_on_dashboard = models.BooleanField(default=False, verbose_name="হোমপেজ নোটিশ বোর্ডে দেখাবে?")
    is_active = models.BooleanField(default=True, verbose_name="অ্যাক্টিভ আছে?")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="প্রকাশের তারিখ")
    
    def __str__(self): return self.title
    
    class Meta:
        verbose_name_plural = "১. নোটিশ বোর্ড"
        ordering = ['-created_at']

# ২. স্লাইডার
class Slider(models.Model):
    title = models.CharField(max_length=200, verbose_name="স্লাইডার শিরোনাম")
    image = models.ImageField(upload_to='sliders/', verbose_name="স্লাইডার ইমেজ")
    is_active = models.BooleanField(default=True, verbose_name="অ্যাক্টিভ আছে?")
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self): return self.title
    class Meta: 
        verbose_name_plural = "৫. হোমপেজ স্লাইডার"

# ৩. ইভেন্ট ভিত্তিক ফটোগ্যালারি
class GalleryCategory(models.Model):
    name = models.CharField(max_length=100, verbose_name="ইভেন্টের নাম (ফোল্ডার)")
    cover_image = models.ImageField(upload_to='gallery/covers/', verbose_name="কভার ফটো")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return self.name
    class Meta: 
        verbose_name_plural = "৬. গ্যালারি ইভেন্ট/ফোল্ডার"

class GalleryImage(models.Model):
    category = models.ForeignKey(GalleryCategory, related_name='images', on_delete=models.CASCADE, verbose_name="ইভেন্ট নির্বাচন করুন")
    image = models.ImageField(upload_to='gallery/photos/', verbose_name="ছবি")
    caption = models.CharField(max_length=100, blank=True, verbose_name="ছবির ক্যাপশন (ঐচ্ছিক)")

    def __str__(self): return f"Image for {self.category.name}"
    class Meta: 
        verbose_name_plural = "গ্যালারি ছবিসমূহ"

# ৪. আমাদের সম্পর্কে ও বিদ্যালয়ের তথ্য
class SchoolInfo(models.Model):
    title = models.CharField(max_length=200, default="আমাদের সম্পর্কে", verbose_name="শিরোনাম")
    description = models.TextField(verbose_name="স্কুলের বর্ণনা/ইতিহাস")
    address = models.CharField(max_length=255, default="বয়রা, খুলনা, বাংলাদেশ", verbose_name="ঠিকানা")
    phone_main = models.CharField(max_length=20, default="+৮৮০", verbose_name="প্রধান ফোন নম্বর")
    phone_alt = models.CharField(max_length=20, blank=True, null=True, verbose_name="বিকল্প ফোন নম্বর")
    email = models.EmailField(default="info@example.com", verbose_name="অফিসিয়াল ইমেইল")
    map_url = models.TextField(blank=True, null=True, verbose_name="গুগল ম্যাপ এমবেড লিঙ্ক (iframe code)")
    facebook_url = models.URLField(blank=True, null=True, verbose_name="ফেসবুক পেজ লিঙ্ক")
    youtube_url = models.URLField(blank=True, null=True, verbose_name="ইউটিউব চ্যানেল লিঙ্ক")
    
    def __str__(self): return self.title
    class Meta: 
        verbose_name_plural = "৭. বিদ্যালয় পরিচিতি ও তথ্য"

class AboutImage(models.Model):
    school_info = models.ForeignKey(SchoolInfo, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='about_slider/', verbose_name="স্লাইডার ছবি")

# ৫. মূল শিক্ষক ও কর্মচারী মডেল
class Teacher(models.Model):
    TYPE_CHOICES = (
        ('HEAD', 'প্রতিষ্ঠান প্রধান'),
        ('TEACHER', 'সহকারী শিক্ষক'),
        ('STAFF', 'কর্মচারী'),
    )
    teacher_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='TEACHER', verbose_name="ধরণ")
    name = models.CharField(max_length=100, verbose_name="নাম")
    designation = models.CharField(max_length=100, verbose_name="পদবী")
    image = models.ImageField(upload_to='teachers/', verbose_name="ছবি")
    phone = models.CharField(max_length=15, blank=True, null=True, verbose_name="ফোন নম্বর")
    email = models.EmailField(blank=True, null=True, verbose_name="ইমেইল")
    order = models.PositiveIntegerField(default=0, verbose_name="ক্রমিক নং (সিরিয়াল)")

    def __str__(self): return self.name
    class Meta:
        verbose_name_plural = "৫. সকল তালিকা"
        ordering = ['order']

# ৬. পরীক্ষার রুটিন
class ExamRoutine(models.Model):
    CLASS_CHOICES = (
        ('6', 'ষষ্ঠ শ্রেণী'),
        ('7', 'সপ্তম শ্রেণী'),
        ('8', 'অষ্টম শ্রেণী'),
        ('9', 'নবম শ্রেণী'),
        ('10', 'দশম শ্রেণী'),
    )
    title = models.CharField(max_length=200, verbose_name="পরীক্ষার শিরোনাম (উদা: বার্ষিক পরীক্ষা ২০২৬)")
    target_class = models.CharField(max_length=2, choices=CLASS_CHOICES, verbose_name="শ্রেণী নির্বাচন করুন")
    pdf_file = models.FileField(upload_to='exam_routines/', verbose_name="রুটিন পিডিএফ (PDF)")
    
    show_on_ticker = models.BooleanField(default=True, verbose_name="নিউজ টিকারে দেখাবে?")
    show_on_notice = models.BooleanField(default=True, verbose_name="নোটিশ বোর্ডে দেখাবে?")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="আপলোডের তারিখ")

    def __str__(self): return f"Class {self.target_class} - {self.title}"
    class Meta:
        verbose_name_plural = "৬. পরীক্ষার রুটিন"
        ordering = ['-created_at']

# ৭. শিক্ষার্থী কর্নার তথ্য
class StudentCornerData(models.Model):
    CATEGORY_CHOICES = [
        ('INFO', 'শ্রেণী ও লিঙ্গভিত্তিক শিক্ষার্থী তথ্য'),
        ('SEAT', 'শ্রেণী ভিত্তিক আসন সংখ্যা'),
        ('DRESS', 'স্কুল-কলেজের ড্রেস সম্পর্কিত তথ্য'),
        ('CLASS_ROUTINE', 'ক্লাস রুটিন'),
        ('SYLLABUS', 'সিলেবাস'),
        ('HOLIDAY', 'ছুটির তালিকা'),
    ]
    
    title = models.CharField(max_length=255, verbose_name="ফাইলের শিরোনাম")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name="ক্যাটাগরি নির্বাচন করুন")
    pdf_file = models.FileField(upload_to='student_corner/pdfs/', verbose_name="PDF ফাইল আপলোড করুন")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="আপলোডের তারিখ")

    def __str__(self):
        return f"{self.get_category_display()} - {self.title}"

    class Meta:
        verbose_name_plural = "১০. শিক্ষার্থী কর্নার তথ্য (সিলেবাস, রুটিন ইত্যাদি)"
        ordering = ['-created_at']

# ৮. ভর্তি তথ্য (Admission Info)
class AdmissionInfo(models.Model):
    CATEGORY_CHOICES = [
        ('form', 'ভর্তি আবেদন ফরম'),
        ('guide', 'ভর্তি নির্দেশিকা'),
        ('result', 'ভর্তি পরীক্ষার ফলাফল'),
        ('fees', 'বেতন ও ফি সমূহ'),
    ]

    title = models.CharField(max_length=255, verbose_name="ফাইলের শিরোনাম")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name="ক্যাটাগরি")
    pdf_file = models.FileField(upload_to='admission/pdfs/', verbose_name="পিডিএফ ফাইল")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="আপলোড তারিখ")

    def __str__(self):
        return f"{self.title} - {self.get_category_display()}"

    class Meta:
        verbose_name_plural = "৮. ভর্তি সংক্রান্ত তথ্য (ফরম, ফলাফল ইত্যাদি)"
        ordering = ['-created_at']

# --- নতুন সংযোজন: ৯. ফলাফল তথ্য (Result Data) ---
class ResultData(models.Model):
    CATEGORY_CHOICES = [
        ('public', 'পাবলিক পরীক্ষার ফলাফল'),
        ('internal', 'স্কুল ও কলেজের ফলাফল'),
    ]

    title = models.CharField(max_length=255, verbose_name="ফলাফলের শিরোনাম (উদা: এসএসসি ফলাফল ২০২৫)")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name="ফলাফলের ধরন")
    file = models.FileField(upload_to='results/pdfs/', verbose_name="ফলাফল পিডিএফ (PDF)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="প্রকাশের তারিখ")

    def __str__(self):
        return f"{self.get_category_display()} - {self.title}"

    class Meta:
        verbose_name_plural = "১১. সকল পরীক্ষার ফলাফল (পাবলিক ও অভ্যন্তরীণ)"
        ordering = ['-created_at']

# ১০. প্রাপ্ত অভিযোগ বা যোগাযোগ বার্তা
class ContactMessage(models.Model):
    name = models.CharField(max_length=100, verbose_name="নাম")
    phone = models.CharField(max_length=15, verbose_name="মোবাইল নম্বর")
    subject = models.CharField(max_length=200, verbose_name="বিষয়")
    message = models.TextField(verbose_name="বার্তা/অভিযোগ")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="জমার সময়")

    def __str__(self): return f"{self.name} - {self.subject}"
    class Meta:
        verbose_name_plural = "৪. প্রাপ্ত অভিযোগ ও বার্তা"
        ordering = ['-created_at']

# --- প্রক্সি মডেলসমূহ ---
class Headmaster(Teacher):
    class Meta:
        proxy = True
        verbose_name = "প্রতিষ্ঠান প্রধান"
        verbose_name_plural = "৯. প্রতিষ্ঠান প্রধান"

class GeneralTeacher(Teacher):
    class Meta:
        proxy = True
        verbose_name = "সহকারী শিক্ষক"
        verbose_name_plural = "২. সহকারী শিক্ষকবৃন্দ"

class Staff(Teacher):
    class Meta:
        proxy = True
        verbose_name = "কর্মচারী"
        verbose_name_plural = "৩. কর্মচারীবৃন্দ"