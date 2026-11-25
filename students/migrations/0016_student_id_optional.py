from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0015_student_old_student_year'),
    ]

    operations = [
        migrations.AlterField(
            model_name='student',
            name='student_id',
            field=models.CharField(
                blank=True,
                max_length=7,
                unique=True,
                verbose_name='Student ID (7 Digits)',
            ),
        ),
    ]