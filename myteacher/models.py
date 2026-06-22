from django.db import models
from students.models import Student
import random
import datetime
from decimal import Decimal
from django.conf import settings

# 1. Subject Model
class Subject(models.Model):
    TYPE_CHOICES = [
        ('1', '1st'),
        ('2', '2nd'),
        ('4', '4th'),
        ('0', 'NA'),
    ]
    
    RELIGION_CHOICES = [
        ('None', 'None'),
        ('Islam', 'Islam'),
        ('Hindu', 'Hindu'),
        ('Buddhist', 'Buddhist'),
        ('Christian', 'Christian'),
    ]
    
    CLASS_CHOICES = [
        ('6', 'Class 6'),
        ('7', 'Class 7'),
        ('8', 'Class 8'),
        ('9', 'Class 9'),
        ('10', 'Class 10'),
    ]

    subject_name = models.CharField(max_length=100, verbose_name="Subject Name")
    subject_type = models.CharField(max_length=1, choices=TYPE_CHOICES, verbose_name="Type")
    religion = models.CharField(max_length=10, choices=RELIGION_CHOICES, default='None', verbose_name="Religion")
    class_level = models.CharField(max_length=2, choices=CLASS_CHOICES, verbose_name="Class")
    has_practical = models.BooleanField(default=False, verbose_name="Has Practical?")
    full_mark = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Full Mark")

    def get_default_full_mark(self):
        name = self.subject_name.strip().lower()
        if self.class_level in ['6', '7', '8']:
            if 'bangla' in name or 'english' in name:
                return Decimal('150.00')
            if 'ict' in name or 'computer' in name:
                return Decimal('50.00')
            if 'agriculture' in name:
                return Decimal('50.00')
            return Decimal('100.00')

        if self.class_level in ['9', '10']:
            if 'bangla' in name:
                return Decimal('200.00')
            if 'english' in name:
                return Decimal('100.00')
            if 'ict' in name or 'computer' in name:
                return Decimal('50.00')
            if 'agriculture' in name:
                return Decimal('100.00')
            return Decimal('100.00')

        return Decimal('100.00')

    @property
    def full_mark_value(self):
        return self.full_mark if self.full_mark is not None else self.get_default_full_mark()

    def infer_religion_from_name(self):
        name = self.subject_name.strip().lower()
        if 'islam' in name:
            return 'Islam'
        if 'hindu' in name:
            return 'Hindu'
        if 'buddhist' in name:
            return 'Buddhist'
        if 'christian' in name:
            return 'Christian'
        return 'None'

    @property
    def effective_religion(self):
        if self.religion and self.religion != 'None':
            return self.religion
        return self.infer_religion_from_name()

    @property
    def is_religion_based(self):
        return self.effective_religion != 'None'

    def __str__(self):
        type_label = self.get_subject_type_display() if hasattr(self, 'get_subject_type_display') else None
        religion_label = self.get_religion_display() if hasattr(self, 'get_religion_display') else self.religion
        parts = [self.subject_name]
        if type_label and type_label not in ('NA', ''):
            parts.append(type_label)
        if self.is_religion_based:
            parts.append(f"({religion_label})")
        parts.append(f"(Class {self.class_level})")
        return ' '.join(parts)

    class Meta:
        verbose_name = "Subject"
        verbose_name_plural = "Subjects"

# 2. Mark Model
class Mark(models.Model):
    def generate_mark_id():
        return random.randint(100000, 999999)

    mark_id = models.CharField(
        max_length=6, 
        default=generate_mark_id, 
        unique=True, 
        primary_key=True,
        verbose_name="Mark ID"
    )
    
    EXAM_CHOICES = [
        ('Half Yearly', 'Half Yearly'),
        ('Annual', 'Annual'),
        ('Pretest', 'Pretest'),
        ('Test', 'Test'),
    ]
    
    exam_type = models.CharField(max_length=20, choices=EXAM_CHOICES, verbose_name="Exam Type", default='Half Yearly')
    exam_year = models.IntegerField(default=datetime.date.today().year, verbose_name="Exam Year")
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, verbose_name="Student")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, verbose_name="Subject")
    
    objective_mark = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    subjective_mark = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    class_test_mark = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    practical_mark = models.DecimalField(max_digits=5, decimal_places=2, default=0, null=True, blank=True)
    
    @property
    def total_mark(self):
        practical = self.practical_mark if self.practical_mark else 0
        return self.objective_mark + self.subjective_mark + self.class_test_mark + practical

    def clean(self):
        from django.core.exceptions import ValidationError
        subject_religion = self.subject.effective_religion
        if self.subject.is_religion_based and self.student.religion != subject_religion:
            raise ValidationError({
                'student': f"Student religion must match subject religion ({subject_religion}).",
                'subject': f"Subject religion must match student religion ({self.student.religion}).",
            })

        if self.subject.is_religion_based:
            existing = Mark.objects.filter(
                student=self.student,
                exam_type=self.exam_type,
                exam_year=self.exam_year,
            ).filter(
                models.Q(subject__religion=subject_religion) |
                models.Q(subject__religion='None', subject__subject_name__icontains=subject_religion)
            )
            if self.pk is not None:
                existing = existing.exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError({
                    'subject': 'A religion-based subject mark already exists for this student in the same exam and year.',
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.full_name} - {self.subject.subject_name} ({self.total_mark}) - {self.exam_type}"

    class Meta:
        verbose_name = "Student Mark"
        verbose_name_plural = "Student Marks"

# 3. Teacher Model
class Teacher(models.Model):
    CLASS_CHOICES = [
        ('6', 'Class 6'), ('7', 'Class 7'), 
        ('8', 'Class 8'), ('9', 'Class 9'), ('10', 'Class 10'),
    ]
    
    DESIGNATION_CHOICES = [
        ('Headmaster', 'Headmaster'),
        ('Assistant Headmaster', 'Assistant Headmaster'),
        ('Senior Teacher', 'Senior Teacher'),
        ('Assistant Teacher', 'Assistant Teacher'),
    ]
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="System User")
    teacher_id = models.CharField(max_length=20, unique=True, verbose_name="Teacher ID")
    teacher_name = models.CharField(max_length=100, verbose_name="Teacher Name")
    designation = models.CharField(max_length=50, choices=DESIGNATION_CHOICES, verbose_name="Designation")
    mobile = models.CharField(max_length=15, verbose_name="Mobile Number")
    email = models.EmailField(unique=True, verbose_name="Email")
    teacher_img = models.ImageField(upload_to='teachers/', verbose_name="Teacher Photo")
    assigned_class = models.CharField(max_length=2, choices=CLASS_CHOICES, verbose_name="Assigned Class")
    
    is_class_teacher = models.BooleanField(default=False, verbose_name="Is Class Teacher?")
    class_teacher_of = models.CharField(
        max_length=2, 
        choices=CLASS_CHOICES, 
        null=True, 
        blank=True, 
        verbose_name="Class Teacher of (Class)"
    )

    def __str__(self):
        return f"{self.teacher_name} ({self.designation})"
    
    def get_assigned_classes(self):
        """Get all classes assigned to this teacher through TeacherClassAssignment"""
        return TeacherClassAssignment.objects.filter(teacher=self).values_list('class_level', flat=True).distinct()
    
    def get_assigned_subjects_for_class(self, class_level):
        """Get all subjects assigned to this teacher for a specific class"""
        return TeacherSubjectAssignment.objects.filter(
            teacher=self, 
            subject__class_level=class_level
        ).values_list('subject', flat=True).distinct()

# 4. Teacher Class Assignment Model (NEW)
class TeacherClassAssignment(models.Model):
    CLASS_CHOICES = [
        ('6', 'Class 6'), ('7', 'Class 7'), 
        ('8', 'Class 8'), ('9', 'Class 9'), ('10', 'Class 10'),
    ]
    
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, verbose_name="Teacher", related_name="class_assignments")
    class_level = models.CharField(max_length=2, choices=CLASS_CHOICES, verbose_name="Class")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Assigned On")

    def __str__(self):
        return f"{self.teacher.teacher_name} → Class {self.class_level}"

    class Meta:
        verbose_name = "Teacher Class Assignment"
        verbose_name_plural = "Teacher Class Assignments"
        unique_together = ('teacher', 'class_level')

# 5. Assignment Model (UPDATED)
class TeacherSubjectAssignment(models.Model):
    def generate_assign_id():
        return random.randint(100000, 999999)

    assisngsubid = models.CharField(
        max_length=6, 
        default=generate_assign_id, 
        unique=True, 
        primary_key=True,
        verbose_name="Assign ID"
    )
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, verbose_name="Teacher")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, verbose_name="Subject")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Assigned On")

    def __str__(self):
        return f"{self.teacher.teacher_name} - {self.subject.subject_name} (Class {self.subject.class_level})"

    class Meta:
        verbose_name = "Subject Assignment"
        verbose_name_plural = "Subject Assignments"
        unique_together = ('teacher', 'subject')

        verbose_name_plural = "Subject Assignments"



class ExamRoutine(models.Model):
    CLASS_CHOICES = [(str(i), f'Class {i}') for i in range(6, 11)]
    GROUP_CHOICES = [('Science', 'Science'), ('Commerce', 'Commerce'), ('Arts', 'Arts'), ('', 'General')]
    EXAM_CHOICES = [('Half Yearly', 'Half Yearly'), ('Annual Exam', 'Annual Exam'), ('Test Exam', 'Test Exam')]

    class_name = models.CharField(max_length=2, choices=CLASS_CHOICES, default='6')
    group_name = models.CharField(max_length=20, choices=GROUP_CHOICES, blank=True, null=True)
    exam_type = models.CharField(max_length=20, choices=EXAM_CHOICES, default='')
    exam_year = models.IntegerField(default=2026)
    subject_name = models.CharField(max_length=100, default="")
    subject_code = models.CharField(max_length=20, blank=True, default="")
    exam_date = models.DateField()
    exam_time = models.CharField(max_length=50, default="10:00 AM")

    def __str__(self):
        return f"{self.subject_name} - Class {self.class_name}"