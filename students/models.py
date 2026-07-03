import random
import string

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Q


CLASS_PROMOTION_MAP = {
    '6': '7',
    '7': '8',
    '8': '9',
    '9': '10',
}


class Student(models.Model):
    CLASS_CHOICES = [
        ('6', 'Class 6'),
        ('7', 'Class 7'),
        ('8', 'Class 8'),
        ('9', 'Class 9'),
        ('10', 'Class 10'),
    ]

    GROUP_CHOICES = [
        (None, 'None'),
        ('Science', 'Science'),
        ('Arts', 'Arts'),
        ('Commerce', 'Commerce'),
    ]

    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other'),
    ]

    RELIGION_CHOICES = [
        ('Islam', 'Islam'),
        ('Hindu', 'Hindu'),
        ('Buddhist', 'Buddhist'),
        ('Christian', 'Christian'),
    ]

    photo = models.ImageField(upload_to='students/', verbose_name="Student Photo")
    full_name = models.CharField(max_length=100, verbose_name="Full Name")
    father_name = models.CharField(max_length=100, verbose_name="Father's Name")
    mother_name = models.CharField(max_length=100, verbose_name="Mother's Name")
    student_id = models.CharField(max_length=7, unique=True, verbose_name="Student ID (7 Digits)")
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='Male', verbose_name="Gender")
    date_of_birth = models.DateField(null=True, blank=True, verbose_name="Date of Birth")
    current_class = models.CharField(max_length=2, choices=CLASS_CHOICES, verbose_name="Class")
    class_roll = models.PositiveIntegerField(verbose_name="Class Roll")
    shift = models.CharField(max_length=10, default='Day', verbose_name="Shift")
    mobile_num = models.CharField(max_length=15, verbose_name="Mobile Number")
    group = models.CharField(max_length=20, choices=GROUP_CHOICES, null=True, blank=True, verbose_name="Group")
    religion = models.CharField(max_length=10, choices=RELIGION_CHOICES, default='Islam', verbose_name="Religion")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='student_profile',
        verbose_name='System User',
    )
    generated_password = models.CharField(max_length=50, blank=True, null=True, verbose_name='Auto Generated Password')
    login_enabled = models.BooleanField(default=True, verbose_name='Login Enabled')
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self):
        return f"{self.full_name} ({self.student_id})"

    @property
    def username(self):
        return self.user.username if self.user else self.student_id

    @staticmethod
    def generate_password(length=8):
        # Generate numeric-only password (digits only) as requested
        digits = string.digits
        return ''.join(random.choice(digits) for _ in range(length))

    def ensure_login_credentials(self):
        user_model = get_user_model()
        password = self.generated_password or self.generate_password()

        if self.user is None:
            username = self.student_id
            existing_user = user_model.objects.filter(username=username).first()
            if existing_user:
                self.user = existing_user
                self.user.set_password(password)
                self.user.save(update_fields=['password'])
            else:
                counter = 1
                while user_model.objects.filter(username=username).exists():
                    username = f"{self.student_id}{counter}"
                    counter += 1
                self.user = user_model.objects.create_user(username=username, password=password)
        else:
            self.user.set_password(password)
            self.user.save(update_fields=['password'])

        self.generated_password = password
        self.save(update_fields=['user', 'generated_password'])
        return self.user, password

    def set_login_password(self, password):
        if not self.user:
            self.ensure_login_credentials()
        self.user.set_password(password)
        self.user.save(update_fields=['password'])
        self.generated_password = password
        super().save(update_fields=['generated_password'])
        return self.user

    def save(self, *args, **kwargs):
        new_record = self.pk is None
        super().save(*args, **kwargs)
        if self.user is None and self.login_enabled and self.student_id:
            self.ensure_login_credentials()

    def set_login_password(self, raw_password):
        if not raw_password:
            return
        if self.user is None:
            self.ensure_login_credentials()
        self.user.set_password(raw_password)
        self.user.save(update_fields=['password'])
        self.generated_password = raw_password
        self.save(update_fields=['generated_password'])

    def promote_to_next_class(self):
        next_class = CLASS_PROMOTION_MAP.get(self.current_class)
        if not next_class:
            return False

        previous_class = self.current_class
        self.current_class = next_class
        self.save(update_fields=['current_class'])
        StudentPromotionHistory.objects.create(student=self, from_class=previous_class, to_class=next_class)
        return True

    def get_result_cards(self):
        Mark = apps.get_model('myteacher', 'Mark')
        return Mark.objects.filter(student=self).select_related('subject').order_by('-exam_year', 'exam_type', 'subject__subject_name')

    def get_admit_cards(self):
        return self.saved_admit_cards.order_by('-exam_year', 'exam_type')

    def save_admit_card(self, exam_type, exam_year, exam_title):
        admit_card, _ = StudentAdmitCard.objects.update_or_create(
            student=self,
            exam_type=exam_type,
            exam_year=exam_year,
            defaults={
                'exam_title': exam_title,
                'class_level': self.current_class,
            }
        )
        return admit_card

    def get_routines(self):
        ExamRoutine = apps.get_model('myteacher', 'ExamRoutine')
        student_group = self.group if self.group else 'General'
        return ExamRoutine.objects.filter(
            class_name=self.current_class
        ).filter(
            Q(group_name=student_group) | Q(group_name='General') | Q(group_name='') | Q(group_name__isnull=True)
        ).order_by('exam_date')

    class Meta:
        verbose_name = 'Student'
        verbose_name_plural = 'Students'
        ordering = ['class_roll', 'full_name']


class StudentAdmitCard(models.Model):
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='saved_admit_cards', verbose_name='Student')
    class_level = models.CharField(max_length=2, choices=Student.CLASS_CHOICES, verbose_name='Class')
    exam_type = models.CharField(max_length=50, verbose_name='Exam Type')
    exam_year = models.IntegerField(verbose_name='Exam Year')
    exam_title = models.CharField(max_length=100, verbose_name='Exam Title')
    generated_at = models.DateTimeField(auto_now=True, verbose_name='Generated On')

    def __str__(self):
        return f'{self.student.full_name} — {self.exam_title}'

    @property
    def display_name(self):
        return f'Class {self.class_level} • {self.exam_title} ({self.exam_year})'

    class Meta:
        verbose_name = 'Saved Admit Card'
        verbose_name_plural = 'Saved Admit Cards'
        unique_together = ('student', 'exam_type', 'exam_year')
        ordering = ['-exam_year', 'exam_type', 'student__class_roll']


class StudentPromotionHistory(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='promotion_history', verbose_name='Student')
    from_class = models.CharField(max_length=2, choices=Student.CLASS_CHOICES, verbose_name='From Class')
    to_class = models.CharField(max_length=2, choices=Student.CLASS_CHOICES, verbose_name='To Class')
    promoted_at = models.DateTimeField(auto_now_add=True, verbose_name='Promoted On')

    def __str__(self):
        return f"{self.student.full_name}: {self.from_class} → {self.to_class}"

    class Meta:
        verbose_name = 'Student Promotion History'
        verbose_name_plural = 'Student Promotion Histories'
        ordering = ['-promoted_at']


class StudentAdmitCardSetting(models.Model):
    class_level = models.CharField(max_length=2, choices=Student.CLASS_CHOICES, verbose_name='Class')
    exam_type = models.CharField(max_length=50, verbose_name='Exam Type')
    exam_year = models.IntegerField(verbose_name='Exam Year')
    is_enabled = models.BooleanField(default=False, verbose_name='Enable Admit Card for Students')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created On')

    @property
    def display_name(self):
        return f'Class {self.class_level} • {self.exam_type} • {self.exam_year}'

    def __str__(self):
        return self.display_name

    class Meta:
        verbose_name = 'Student Admit Card Setting'
        verbose_name_plural = 'Student Admit Card Settings'
        unique_together = ('class_level', 'exam_type', 'exam_year')
        ordering = ['-exam_year', 'exam_type', 'class_level']


class StudentTicker(models.Model):
    title = models.CharField(max_length=120, blank=True, verbose_name='Ticker Title')
    message = models.TextField(verbose_name='Ticker Message')
    show_to_all = models.BooleanField(default=False, verbose_name='Show to All Students')
    target_students = models.ManyToManyField(
        Student,
        blank=True,
        related_name='tickers',
        verbose_name='Target Students',
        help_text='Leave blank if showing to all students, otherwise select specific students.'
    )
    is_active = models.BooleanField(default=True, verbose_name='Active')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created On')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated On')

    def __str__(self):
        return self.title or self.message[:50]

    class Meta:
        verbose_name = 'Student Ticker'
        verbose_name_plural = 'Student Tickers'
        ordering = ['-is_active', '-updated_at']
