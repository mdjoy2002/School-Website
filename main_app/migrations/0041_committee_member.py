from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main_app', '0040_leadershipprofile_caption'),
    ]

    operations = [
        migrations.CreateModel(
            name='CommitteeMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(
                    choices=[
                        ('PRESIDENT', 'সভাপতি'),
                        ('TEACHER_MEMBER', 'সাধারণ শিক্ষক সদস্য'),
                        ('GUARDIAN_MEMBER', 'অভিভাবক সদস্য'),
                        ('SECRETARY', 'সদস্য সচিব'),
                    ],
                    max_length=20,
                    verbose_name='কমিটির বিভাগ',
                )),
                ('name', models.CharField(max_length=150, verbose_name='নাম')),
                ('designation', models.CharField(max_length=150, verbose_name='পদবি')),
                ('phone', models.CharField(blank=True, max_length=20, verbose_name='ফোন নম্বর')),
                ('about', models.TextField(blank=True, verbose_name='সদস্য সম্পর্কে')),
                ('image', models.ImageField(blank=True, upload_to='committee_members/', verbose_name='ছবি')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='ক্রমিক')),
            ],
            options={
                'verbose_name': 'কমিটির সদস্য',
                'verbose_name_plural': 'কমিটিবৃন্দ',
                'ordering': ['order', 'name'],
            },
        ),
    ]
