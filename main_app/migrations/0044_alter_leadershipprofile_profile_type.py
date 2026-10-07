from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main_app", "0043_entry_popup_image"),
    ]

    operations = [
        migrations.AlterField(
            model_name="leadershipprofile",
            name="profile_type",
            field=models.CharField(
                choices=[
                    ("FOUNDER", "প্রতিষ্ঠাতা"),
                    ("HEADMASTER", "প্রধান শিক্ষক"),
                    ("PRESIDENT", "সভাপতি"),
                    ("COMMITTEE", "ম্যানেজিং কমিটি"),
                ],
                max_length=20,
                unique=True,
                verbose_name="প্রোফাইলের ধরন",
            ),
        ),
    ]
