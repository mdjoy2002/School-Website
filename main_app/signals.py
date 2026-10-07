from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import (
    AdmissionInfo,
    CommitteeMember,
    EntryPopupImage,
    ExamRoutine,
    GalleryCategory,
    GalleryImage,
    LeadershipProfile,
    Notice,
    ResultData,
    SchoolInfo,
    Slider,
    StudentCornerData,
    Teacher,
    TickerNews,
)


def touch_school_info_update(**kwargs):
    if kwargs.get('sender') is SchoolInfo:
        return

    school_info = SchoolInfo.objects.first()
    if not school_info:
        school_info = SchoolInfo.objects.create(
            title='আমাদের সম্পর্কে',
            description='স্কুলের তথ্য',
            address='বয়রা, খুলনা, বাংলাদেশ',
            phone_main='+৮৮০',
            email='info@example.com',
        )

    school_info.last_updated = timezone.now()
    school_info.save(update_fields=['last_updated'])


@receiver(post_save, sender=Notice)
@receiver(post_delete, sender=Notice)
def notice_update(sender, **kwargs):
    touch_school_info_update(sender=sender, **kwargs)


@receiver(post_save, sender=TickerNews)
@receiver(post_delete, sender=TickerNews)
def ticker_update(sender, **kwargs):
    touch_school_info_update(sender=sender, **kwargs)


@receiver(post_save, sender=Slider)
@receiver(post_delete, sender=Slider)
def slider_update(sender, **kwargs):
    touch_school_info_update(sender=sender, **kwargs)


@receiver(post_save, sender=EntryPopupImage)
@receiver(post_delete, sender=EntryPopupImage)
def entry_popup_update(sender, **kwargs):
    touch_school_info_update(sender=sender, **kwargs)


@receiver(post_save, sender=GalleryCategory)
@receiver(post_delete, sender=GalleryCategory)
def gallery_category_update(sender, **kwargs):
    touch_school_info_update(sender=sender, **kwargs)


@receiver(post_save, sender=GalleryImage)
@receiver(post_delete, sender=GalleryImage)
def gallery_image_update(sender, **kwargs):
    touch_school_info_update(sender=sender, **kwargs)


@receiver(post_save, sender=LeadershipProfile)
@receiver(post_delete, sender=LeadershipProfile)
def leadership_profile_update(sender, **kwargs):
    touch_school_info_update(sender=sender, **kwargs)


@receiver(post_save, sender=CommitteeMember)
@receiver(post_delete, sender=CommitteeMember)
def committee_member_update(sender, **kwargs):
    touch_school_info_update(sender=sender, **kwargs)


@receiver(post_save, sender=Teacher)
@receiver(post_delete, sender=Teacher)
def teacher_update(sender, **kwargs):
    touch_school_info_update(sender=sender, **kwargs)


@receiver(post_save, sender=ExamRoutine)
@receiver(post_delete, sender=ExamRoutine)
def exam_routine_update(sender, **kwargs):
    touch_school_info_update(sender=sender, **kwargs)


@receiver(post_save, sender=StudentCornerData)
@receiver(post_delete, sender=StudentCornerData)
def student_corner_update(sender, **kwargs):
    touch_school_info_update(sender=sender, **kwargs)


@receiver(post_save, sender=AdmissionInfo)
@receiver(post_delete, sender=AdmissionInfo)
def admission_info_update(sender, **kwargs):
    touch_school_info_update(sender=sender, **kwargs)


@receiver(post_save, sender=ResultData)
@receiver(post_delete, sender=ResultData)
def result_data_update(sender, **kwargs):
    touch_school_info_update(sender=sender, **kwargs)
