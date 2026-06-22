from django.apps import apps
from django.db import models
from django.db.models import Q


# Create your models here.

class Student(models.Model):
    # ক্লাস ও সেকশনের জন্য চয়েস
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

    RELIGION_CHOICES = [
        ('Islam', 'Islam'),
        ('Hindu', 'Hindu'),
        ('Buddhist', 'Buddhist'),
        ('Christian', 'Christian'),
    ]

    # প্রয়োজনীয় ফিল্ডসমূহ
    photo = models.ImageField(upload_to='students/', verbose_name="Student Photo")
    full_name = models.CharField(max_length=100, verbose_name="Full Name")
    father_name = models.CharField(max_length=100, verbose_name="Father's Name")
    mother_name = models.CharField(max_length=100, verbose_name="Mother's Name")
    
    # 7 digit student ID (Manual Input)
    student_id = models.CharField(max_length=7, unique=True, verbose_name="Student ID (7 Digits)")
    
    current_class = models.CharField(max_length=2, choices=CLASS_CHOICES, verbose_name="Class")
    class_roll = models.PositiveIntegerField(verbose_name="Class Roll") # 01-50 চেক করার জন্য আমরা লজিক অ্যাডমিন প্যানেলে দিতে পারি
    shift = models.CharField(max_length=10, default='Day', verbose_name="Shift")
    mobile_num = models.CharField(max_length=15, verbose_name="Mobile Number")
    group = models.CharField(max_length=20, choices=GROUP_CHOICES, null=True, blank=True, verbose_name="Group")
    religion = models.CharField(max_length=10, choices=RELIGION_CHOICES, default='Islam', verbose_name="Religion")

    def __str__(self):
        return f"{self.full_name} ({self.student_id})"

    def get_routines(self):
        ExamRoutine = apps.get_model('myteacher', 'ExamRoutine')
        student_group = self.group if self.group else 'General'
        return ExamRoutine.objects.filter(
            class_name=self.current_class
        ).filter(
            Q(group_name=student_group) | Q(group_name='General') | Q(group_name='') | Q(group_name__isnull=True)
        ).order_by('exam_date')

    class Meta:
        verbose_name = "Student"
        verbose_name_plural = "Students"
