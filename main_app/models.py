from django.db import models
from django.core.validators import MinValueValidator
from core.compression import CompressedUploadMixin
from .storage import PrivateAdmissionStorage


# ১. নোটিশ বোর্ড
class Notice(CompressedUploadMixin, models.Model):
    title = models.CharField(max_length=200, verbose_name="নোটিশের শিরোনাম")
    description = models.TextField(verbose_name="বিস্তারিত", blank=True, null=True)
    file = models.FileField(upload_to='notices/', verbose_name="পিডিএফ ফাইল (PDF)")
    PDF_FIELDS = ['file']
    
    show_on_ticker = models.BooleanField(default=False, verbose_name="নিউজ টিকারে (সর্বশেষ) দেখাবে?")
    show_on_dashboard = models.BooleanField(default=False, verbose_name="হোমপেজ নোটিশ বোর্ডে দেখাবে?")
    is_new = models.BooleanField(default=False, verbose_name="নতুন নোটিশ?")
    is_active = models.BooleanField(default=True, verbose_name="অ্যাক্টিভ আছে?")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="প্রকাশের তারিখ")
    
    def __str__(self): return self.title
    
    class Meta:
        verbose_name_plural = "১. নোটিশ বোর্ড"
        ordering = ['-created_at']

# ২. টিকার নিউজ
class TickerNews(models.Model):
    title = models.CharField(max_length=255, verbose_name="খবরের শিরোনাম")
    is_active = models.BooleanField(default=True, verbose_name="সক্রিয় কি না")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return self.title

    class Meta:
        verbose_name_plural = "টিকার নিউজ"

# ৩. স্লাইডার
class Slider(CompressedUploadMixin, models.Model):
    title = models.CharField(max_length=200, verbose_name="স্লাইডার শিরোনাম")
    image = models.ImageField(upload_to='sliders/', verbose_name="স্লাইডার ইমেজ")
    IMAGE_FIELDS = ['image']
    is_active = models.BooleanField(default=True, verbose_name="অ্যাক্টিভ আছে?")
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self): return self.title
    class Meta: 
        verbose_name_plural = "৫. হোমপেজ স্লাইডার"


class EntryPopupImage(CompressedUploadMixin, models.Model):
    title = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="ছবির শিরোনাম (ঐচ্ছিক)",
    )
    image = models.ImageField(upload_to='welcome_slider/', verbose_name="ছবি")
    IMAGE_FIELDS = ['image']
    is_active = models.BooleanField(default=True, verbose_name="অ্যাক্টিভ আছে?")
    order = models.PositiveIntegerField(default=0, verbose_name="ক্রম")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="তৈরির তারিখ")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="সর্বশেষ আপডেট")

    def __str__(self):
        return self.title or self.image.name.rsplit('/', 1)[-1]

    class Meta:
        verbose_name = "Welcome Slider"
        verbose_name_plural = "Welcome Slider"
        ordering = ['order', 'pk']


# ৩. ইভেন্ট ভিত্তিক ফটোগ্যালারি
class GalleryCategory(CompressedUploadMixin, models.Model):
    name = models.CharField(max_length=100, verbose_name="ইভেন্টের নাম (ফোল্ডার)")
    cover_image = models.ImageField(upload_to='gallery/covers/', verbose_name="কভার ফটো")
    IMAGE_FIELDS = ['cover_image']
    created_at = models.DateTimeField(auto_now_add=True)

    # কভার ইমেজ না থাকলে এরর এড়াতে এই প্রপার্টিটি ব্যবহার করুন
    @property
    def get_cover_url(self):
        if self.cover_image and hasattr(self.cover_image, 'url'):
            return self.cover_image.url
        return None

    def __str__(self): return self.name
    class Meta: 
        verbose_name_plural = "৬. গ্যালারি ইভেন্ট/ফোল্ডার"

class GalleryImage(CompressedUploadMixin, models.Model):
    category = models.ForeignKey(GalleryCategory, related_name='images', on_delete=models.CASCADE, verbose_name="ইভেন্ট নির্বাচন করুন")
    image = models.ImageField(upload_to='gallery/photos/', verbose_name="ছবি")
    IMAGE_FIELDS = ['image']
    caption = models.CharField(max_length=100, blank=True, verbose_name="ছবির ক্যাপশন (ঐচ্ছিক)")

    def __str__(self): return f"Image for {self.category.name if self.category else 'Uncategorized'}"
    class Meta: 
        verbose_name_plural = "গ্যালারি ছবিসমূহ"

# ৪. আমাদের সম্পর্কে ও বিদ্যালয়ের তথ্য
class SchoolInfo(models.Model):
    title = models.CharField(max_length=200, default="আমাদের সম্পর্কে", verbose_name="শিরোনাম")
    school_name_bangla = models.CharField(
        max_length=255,
        default="খন্দকার নাসের উদ্দিন মাধ্যমিক বিদ্যালয়",
        verbose_name="স্কুলের নাম (বাংলা)",
    )
    school_name_english = models.CharField(
        max_length=255,
        default="Khondakar Naser Uddin Secondary School",
        verbose_name="স্কুলের নাম (ইংরেজি)",
    )
    school_code = models.CharField(
        max_length=50,
        default="KNS-001",
        verbose_name="স্কুল কোড",
    )
    description = models.TextField(verbose_name="স্কুলের বর্ণনা/ইতিহাস")
    address = models.CharField(max_length=255, default="বয়রা, খুলনা, বাংলাদেশ", verbose_name="ঠিকানা")
    phone_main = models.CharField(max_length=20, default="+৮৮০", verbose_name="প্রধান ফোন নম্বর")
    phone_alt = models.CharField(max_length=20, blank=True, null=True, verbose_name="বিকল্প ফোন নম্বর")
    email = models.EmailField(default="info@example.com", verbose_name="অফিসিয়াল ইমেইল")
    map_url = models.TextField(blank=True, null=True, verbose_name="গুগল ম্যাপ এমবেড লিংক (iframe code)")
    facebook_url = models.URLField(blank=True, null=True, verbose_name="ফেসবুক পেজ লিঙ্ক")
    youtube_url = models.URLField(blank=True, null=True, verbose_name="ইউটিউব চ্যানেল লিঙ্ক")
    last_updated = models.DateTimeField(auto_now=True, verbose_name="সর্বশেষ আপডেট")

    def __str__(self): return self.title
    class Meta:
        verbose_name_plural = "৭. বিদ্যালয় পরিচিতি ও তথ্য"



class LeadershipProfile(CompressedUploadMixin, models.Model):
    PROFILE_TYPES = (
        ('FOUNDER', 'প্রতিষ্ঠাতা'),
        ('HEADMASTER', 'প্রধান শিক্ষক'),
        ('PRESIDENT', 'সভাপতি'),
        ('COMMITTEE', 'ম্যানেজিং কমিটি'),
    )

    profile_type = models.CharField(
        max_length=20,
        choices=PROFILE_TYPES,
        unique=True,
        verbose_name="প্রোফাইলের ধরন",
    )
    name = models.CharField(max_length=150, verbose_name="নাম")
    designation = models.CharField(max_length=150, verbose_name="পদবি")
    caption = models.TextField(blank=True, verbose_name="ক্যাপশন/বার্তা")
    image = models.ImageField(upload_to='leadership/', verbose_name="ছবি")
    IMAGE_FIELDS = ['image']

    def __str__(self):
        return self.get_profile_type_display()

    class Meta:
        verbose_name = "প্রধান শিক্ষক ও ম্যানেজিং কমিটি"
        verbose_name_plural = "প্রধান শিক্ষক ও ম্যানেজিং কমিটি"


class CommitteeMember(CompressedUploadMixin, models.Model):
    CATEGORY_CHOICES = (
        ('PRESIDENT', 'সভাপতি'),
        ('TEACHER_MEMBER', 'সাধারণ শিক্ষক সদস্য'),
        ('GUARDIAN_MEMBER', 'অভিভাবক সদস্য'),
        ('SECRETARY', 'সদস্য সচিব'),
    )

    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        verbose_name="কমিটির বিভাগ",
    )
    name = models.CharField(max_length=150, verbose_name="নাম")
    designation = models.CharField(max_length=150, verbose_name="পদবি")
    phone = models.CharField(max_length=20, blank=True, verbose_name="ফোন নম্বর")
    about = models.TextField(blank=True, verbose_name="সদস্য সম্পর্কে")
    image = models.ImageField(
        upload_to='committee_members/',
        blank=True,
        verbose_name="ছবি",
    )
    IMAGE_FIELDS = ['image']
    order = models.PositiveIntegerField(default=0, verbose_name="ক্রমিক")

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "কমিটির সদস্য"
        verbose_name_plural = "কমিটিবৃন্দ"


class AboutImage(CompressedUploadMixin, models.Model):
    school_info = models.ForeignKey(SchoolInfo, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='about_slider/', verbose_name="স্লাইডার ছবি")
    IMAGE_FIELDS = ['image']

# ৫. মূল শিক্ষক ও কর্মচারী মডেল
class Teacher(CompressedUploadMixin, models.Model):
    TYPE_CHOICES = (
        ('HEAD', 'প্রতিষ্ঠান প্রধান'),
        ('TEACHER', 'সহকারী শিক্ষক'),
        ('STAFF', 'কর্মচারী'),
    )
    DESIGNATION_CHOICES = [
        ('Headmaster', 'প্রতিষ্ঠান প্রধান'),
        ('Assistant Headmaster', 'সহকারী প্রধান শিক্ষক'),
        ('Senior Teacher', 'সিনিয়র শিক্ষক'),
        ('Assistant Teacher', 'সহকারী শিক্ষক'),
        ('Office Staff', 'অফিস স্টাফ'),
        ('Clerk', 'ক্লার্ক'),
        ('Accountant', 'হিসাবরক্ষক'),
        ('Night Guard', 'নৈশ প্রহরী'),
        ('Cleaner', 'পরিচ্ছন্ন কর্মী'),
        ('Aya', 'আয়া'),
    ]
    teacher_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='TEACHER', verbose_name="ধরণ")
    name = models.CharField(max_length=100, verbose_name="নাম")
    designation = models.CharField(max_length=50, choices=DESIGNATION_CHOICES, blank=True, verbose_name="পদবী")
    subject = models.CharField(max_length=200, blank=True, null=True, verbose_name="বিষয়")
    image = models.ImageField(upload_to='teachers/', verbose_name="ছবি")
    IMAGE_FIELDS = ['image']
    phone = models.CharField(max_length=15, blank=True, null=True, verbose_name="ফোন নম্বর")
    email = models.EmailField(blank=True, null=True, verbose_name="ইমেইল")
    order = models.PositiveIntegerField(default=0, verbose_name="ক্রমিক নং (সিরিয়াল)")

    def __str__(self): return self.name
    class Meta:
        verbose_name_plural = "৫. সকল তালিকা"
        ordering = ['order']

# ৬. পরীক্ষার রুটিন
class ExamRoutine(CompressedUploadMixin, models.Model):
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
    PDF_FIELDS = ['pdf_file']
    
    show_on_ticker = models.BooleanField(default=True, verbose_name="নিউজ টিকারে দেখাবে?")
    show_on_notice = models.BooleanField(default=True, verbose_name="নোটিশ বোর্ডে দেখাবে?")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="আপলোডের তারিখ")

    def __str__(self): return f"Class {self.target_class} - {self.title}"
    class Meta:
        verbose_name_plural = "৬. পরীক্ষার রুটিন"
        ordering = ['-created_at']

# ৭. শিক্ষার্থী কর্নার তথ্য
class StudentCornerData(CompressedUploadMixin, models.Model):
    CATEGORY_CHOICES = [
        ('INFO', 'শ্রেণী ও লিঙ্গভিত্তিক শিক্ষার্থী তথ্য'),
        ('SEAT', 'শ্রেণী ভিত্তিক আসন সংখ্যা'),
        ('DRESS', 'স্কুল-কলেজের ড্রেস সম্পর্কিত তথ্য'),
        ('CLASS_ROUTINE', 'ক্লাস রুটিন'),
        ('SYLLABUS', 'সিলেবাস'),
        ('EXAM_ROUTINE', 'পরীক্ষার রুটিন'),
        ('HOLIDAY', 'ছুটির তালিকা'),
    ]
    
    title = models.CharField(max_length=255, verbose_name="ফাইলের শিরোনাম")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name="ক্যাটাগরি নির্বাচন করুন")
    pdf_file = models.FileField(upload_to='student_corner/pdfs/', verbose_name="PDF ফাইল আপলোড করুন")
    PDF_FIELDS = ['pdf_file']
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="আপলোডের তারিখ")

    def __str__(self):
        return f"{self.get_category_display()} - {self.title}"

    class Meta:
        verbose_name_plural = "১০. শিক্ষার্থী কর্নার তথ্য (সিলেবাস, রুটিন ইত্যাদি)"
        ordering = ['-created_at']

# ৮. ভর্তি তথ্য (Admission Info)
class AdmissionInfo(CompressedUploadMixin, models.Model):
    CATEGORY_CHOICES = [
        ('form', 'ভর্তি আবেদন ফরম'),
        ('guide', 'ভর্তি নির্দেশিকা'),
        ('result', 'ভর্তি পরীক্ষার ফলাফল'),
        ('fees', 'বেতন ও ফি সমূহ'),
    ]

    title = models.CharField(max_length=255, verbose_name="ফাইলের শিরোনাম")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name="ক্যাটাগরি")
    pdf_file = models.FileField(upload_to='admission/pdfs/', verbose_name="পিডিএফ ফাইল")
    PDF_FIELDS = ['pdf_file']
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="আপলোড তারিখ")

    def __str__(self):
        return f"{self.title} - {self.get_category_display()}"

    class Meta:
        verbose_name_plural = "৮. ভর্তি সংক্রান্ত তথ্য (ফরম, ফলাফল ইত্যাদি)"
        ordering = ['-created_at']

# ৯. ভর্তি আবেদন
class AdmissionApplication(models.Model):
    ADMISSION_CLASS_CHOICES = [
        ('ষষ্ঠ', 'ষষ্ঠ'),
        ('সপ্তম', 'সপ্তম'),
        ('অষ্টম', 'অষ্টম'),
        ('নবম', 'নবম'),
        ('দশম', 'দশম'),
    ]
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    PAYMENT_STATUS_CHOICES = [
        ('PENDING', 'অপেক্ষমাণ'),
        ('PAID', 'পরিশোধিত'),
        ('UNPAID', 'বকেয়া'),
        ('WAIVED', 'মওকুফ'),
    ]
    SECTION_CHOICES = [
        ('ক', 'ক'),
        ('খ', 'খ'),
        ('গ', 'গ'),
        ('ঘ', 'ঘ'),
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
        ('D', 'D'),
        ('OTHER', 'অন্যান্য'),
    ]

    application_id = models.CharField(max_length=32, unique=True, blank=True, null=True, verbose_name="Admission ID")
    email = models.EmailField(blank=True, verbose_name="আবেদনকারীর ইমেইল")
    admission_class = models.CharField(
        max_length=20,
        choices=ADMISSION_CLASS_CHOICES,
        blank=True,
        null=True,
        verbose_name="আবেদিত শ্রেণি",
    )
    academic_year = models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="শিক্ষাবর্ষ")
    class_roll_number = models.PositiveIntegerField(blank=True, null=True, verbose_name="শ্রেণিভিত্তিক আবেদন রোল")
    application_fee = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="আবেদন ফি (টাকা)",
    )
    application_data = models.JSONField(verbose_name="আবেদনের তথ্য")
    student_photo = models.ImageField(
        storage=PrivateAdmissionStorage(),
        upload_to='admission_applications/photos/',
        verbose_name="শিক্ষার্থীর ছবি",
    )
    pdf_file = models.FileField(
        storage=PrivateAdmissionStorage(),
        upload_to='admission_applications/pdfs/',
        blank=True,
        verbose_name="আবেদন ফরমের PDF",
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name="আবেদনের অবস্থা",
    )
    payment_status = models.CharField(
        max_length=10,
        choices=PAYMENT_STATUS_CHOICES,
        default='UNPAID',
        verbose_name="ভর্তি ফি ও পেমেন্টের অবস্থা",
    )
    assigned_class = models.CharField(
        max_length=20,
        choices=ADMISSION_CLASS_CHOICES,
        blank=True,
        verbose_name="নির্ধারিত শ্রেণি",
    )
    assigned_section = models.CharField(
        max_length=10,
        choices=SECTION_CHOICES,
        blank=True,
        verbose_name="নির্ধারিত শাখা",
    )
    assigned_roll = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="নির্ধারিত রোল",
    )
    approver_name = models.CharField(max_length=150, blank=True, verbose_name="অনুমোদনকারীর নাম")
    admission_confirmed_at = models.DateField(
        null=True,
        blank=True,
        verbose_name="ভর্তি নিশ্চিত হওয়ার তারিখ",
    )
    office_comment = models.TextField(blank=True, verbose_name="মন্তব্য")
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name="আবেদনের সময়")

    def save(self, *args, **kwargs):
        if not self.assigned_class and self.admission_class:
            self.assigned_class = self.admission_class
        super().save(*args, **kwargs)

    def __str__(self):
        return self.application_id or self.application_data.get('student_name_bn', f'আবেদন #{self.pk}')

    class Meta:
        verbose_name = "ভর্তি আবেদন"
        verbose_name_plural = "ভর্তি আবেদনসমূহ"
        ordering = ['-submitted_at']
        constraints = [
            models.UniqueConstraint(
                fields=('admission_class', 'academic_year', 'class_roll_number'),
                name='unique_admission_class_year_roll',
            ),
        ]


class AdmissionSequence(models.Model):
    admission_class = models.CharField(
        max_length=20,
        choices=AdmissionApplication.ADMISSION_CLASS_CHOICES,
        verbose_name="শ্রেণি",
    )
    academic_year = models.PositiveSmallIntegerField(verbose_name="শিক্ষাবর্ষ")
    next_application_number = models.PositiveIntegerField(default=1, verbose_name="পরবর্তী আবেদন নম্বর")
    next_roll_number = models.PositiveIntegerField(default=1, verbose_name="পরবর্তী শ্রেণিভিত্তিক রোল")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('admission_class', 'academic_year'),
                name='unique_admission_sequence_class_year',
            ),
        ]
        verbose_name = "ভর্তি আবেদন সিরিয়াল"
        verbose_name_plural = "ভর্তি আবেদন সিরিয়াল"


class AdmissionApplySettings(models.Model):
    CLASS_FEE_FIELDS = {
        'ষষ্ঠ': 'fee_class_6',
        'সপ্তম': 'fee_class_7',
        'অষ্টম': 'fee_class_8',
        'নবম': 'fee_class_9',
        'দশম': 'fee_class_10',
    }
    CLASS_DOCUMENT_FIELDS = {
        'ষষ্ঠ': 'documents_class_6',
        'সপ্তম': 'documents_class_7',
        'অষ্টম': 'documents_class_8',
        'নবম': 'documents_class_9',
        'দশম': 'documents_class_10',
    }
    singleton_key = models.PositiveSmallIntegerField(
        primary_key=True,
        default=1,
        editable=False,
    )
    is_active = models.BooleanField(default=False, verbose_name="ভর্তি আবেদন চালু আছে")
    application_fee = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        verbose_name="আবেদন ফি (টাকা)",
    )
    fee_class_6 = models.DecimalField(max_digits=8, decimal_places=2, default=0, validators=[MinValueValidator(0)], verbose_name="ষষ্ঠ শ্রেণির আবেদন ফি")
    fee_class_7 = models.DecimalField(max_digits=8, decimal_places=2, default=0, validators=[MinValueValidator(0)], verbose_name="সপ্তম শ্রেণির আবেদন ফি")
    fee_class_8 = models.DecimalField(max_digits=8, decimal_places=2, default=0, validators=[MinValueValidator(0)], verbose_name="অষ্টম শ্রেণির আবেদন ফি")
    fee_class_9 = models.DecimalField(max_digits=8, decimal_places=2, default=0, validators=[MinValueValidator(0)], verbose_name="নবম শ্রেণির আবেদন ফি")
    fee_class_10 = models.DecimalField(max_digits=8, decimal_places=2, default=0, validators=[MinValueValidator(0)], verbose_name="দশম শ্রেণির আবেদন ফি")
    documents_class_6 = models.TextField(blank=True, verbose_name="ষষ্ঠ শ্রেণির প্রয়োজনীয় কাগজপত্র (প্রতি লাইনে একটি)")
    documents_class_7 = models.TextField(blank=True, verbose_name="সপ্তম শ্রেণির প্রয়োজনীয় কাগজপত্র (প্রতি লাইনে একটি)")
    documents_class_8 = models.TextField(blank=True, verbose_name="অষ্টম শ্রেণির প্রয়োজনীয় কাগজপত্র (প্রতি লাইনে একটি)")
    documents_class_9 = models.TextField(blank=True, verbose_name="নবম শ্রেণির প্রয়োজনীয় কাগজপত্র (প্রতি লাইনে একটি)")
    documents_class_10 = models.TextField(blank=True, verbose_name="দশম শ্রেণির প্রয়োজনীয় কাগজপত্র (প্রতি লাইনে একটি)")
    bkash_enabled = models.BooleanField(default=True, verbose_name="বিকাশ পেমেন্ট চালু")
    bkash_number = models.CharField(max_length=30, blank=True, verbose_name="বিকাশ নম্বর")
    nagad_enabled = models.BooleanField(default=True, verbose_name="নগদ পেমেন্ট চালু")
    nagad_number = models.CharField(max_length=30, blank=True, verbose_name="নগদ নম্বর")
    in_school_enabled = models.BooleanField(default=True, verbose_name="স্কুলে পেমেন্ট চালু")
    payment_instructions = models.TextField(blank=True, verbose_name="পেমেন্ট নির্দেশনা")
    ticker_text = models.CharField(
        max_length=200,
        default="অনলাইন ভর্তি আবেদন চলছে — আবেদন করতে এখানে ক্লিক করুন",
        verbose_name="নিউজ টিকারের লেখা",
    )

    def fee_for_class(self, admission_class):
        field_name = self.CLASS_FEE_FIELDS.get(admission_class)
        return getattr(self, field_name) if field_name else 0

    def documents_for_class(self, admission_class):
        field_name = self.CLASS_DOCUMENT_FIELDS.get(admission_class)
        if not field_name:
            return []
        lines = getattr(self, field_name).splitlines()
        return list(dict.fromkeys(line.strip() for line in lines if line.strip()))

    def save(self, *args, **kwargs):
        self.singleton_key = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return "Admission apply"

    class Meta:
        verbose_name = "Admission apply"
        verbose_name_plural = "Admission apply"


# ১০. ফলাফল তথ্য (Result Data)
class ResultData(CompressedUploadMixin, models.Model):
    CATEGORY_CHOICES = [
        ('public', 'পাবলিক পরীক্ষার ফলাফল'),
        ('internal', 'স্কুল ও কলেজের ফলাফল'),
    ]

    title = models.CharField(max_length=255, verbose_name="ফলাফলের শিরোনাম (উদা: এসএসসি ফলাফল ২০২৫)")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name="ফলাফলের ধরন")
    file = models.FileField(upload_to='results/pdfs/', verbose_name="ফলাফল পিডিএফ (PDF)")
    PDF_FIELDS = ['file']
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


class VisitorProfile(models.Model):
    visitor_uuid = models.CharField(max_length=64, unique=True, db_index=True, verbose_name='ভিজিটর ইউইডি')
    ip_address = models.CharField(max_length=45, verbose_name='আইপি ঠিকানা')
    first_visit = models.DateTimeField(auto_now_add=True, verbose_name='প্রথম ভিজিট')
    last_visit = models.DateTimeField(auto_now=True, verbose_name='সর্বশেষ ভিজিট')

    def __str__(self):
        return self.visitor_uuid

    class Meta:
        verbose_name_plural = 'ভিজিটর প্রোফাইল'


class DailyVisitor(models.Model):
    date = models.DateField(verbose_name='তারিখ')
    ip_address = models.CharField(max_length=45, verbose_name='আইপি ঠিকানা')
    session_key = models.CharField(max_length=40, verbose_name='সেশন কী')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='সৃষ্টি সময়')
    visitor_profile = models.ForeignKey(
        VisitorProfile,
        on_delete=models.CASCADE,
        related_name='daily_visits',
    )

    def __str__(self):
        return f"{self.date} - {self.ip_address}"

    class Meta:
        verbose_name_plural = 'দৈনিক ভিজিটর'
        indexes = [
            models.Index(fields=['date'], name='main_app_daily_date_idx'),
            models.Index(fields=['ip_address', 'session_key'], name='main_app_daily_vis_idx'),
        ]
        unique_together = (('date', 'ip_address', 'session_key'),)
