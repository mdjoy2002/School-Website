from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0014_alter_student_blood_group'),
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='old_student_year',
            field=models.PositiveSmallIntegerField(
                blank=True,
                db_index=True,
                null=True,
                verbose_name='Old Student Year',
            ),
        ),
    ]
