import os
import django
os.chdir(r'E:\SchoolWebsite')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()
from students.models import StudentTicker, Student
import django.db.models as dm
s = Student.objects.filter(student_id='1234567').first()
print('student', s)
print('student id', s.student_id if s else None)
print('tickercount', StudentTicker.objects.count())
for t in StudentTicker.objects.all():
    print('ticker', t.pk, repr(t.title), t.show_to_all, t.is_active, list(t.target_students.values_list('student_id', flat=True)))
if s:
    matched = list(StudentTicker.objects.filter(is_active=True).filter(dm.Q(show_to_all=True) | dm.Q(target_students=s)).distinct().values_list('pk', flat=True))
    print('matched ticker ids', matched)
else:
    print('no student')
