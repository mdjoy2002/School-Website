from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main_app', '0041_committee_member'),
    ]

    operations = [
        migrations.AddField(
            model_name='notice',
            name='is_new',
            field=models.BooleanField(default=False, verbose_name='নতুন নোটিশ?'),
        ),
    ]
