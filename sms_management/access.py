from django.core.exceptions import ObjectDoesNotExist

from .models import SMSAccessSettings


def user_can_access_sms(user, teacher=None):
    if user.is_superuser:
        return True

    is_head_teacher = bool(
        teacher
        and teacher.designation in ('Headmaster', 'Assistant Headmaster')
    )
    has_sms_permission = (
        user.is_staff
        and user.has_perm('sms_management.access_sms_dashboard')
    )
    if is_head_teacher or has_sms_permission:
        return True

    if teacher is None:
        try:
            teacher = user.teacher
        except ObjectDoesNotExist:
            return False
    return bool(
        teacher
        and SMSAccessSettings.objects.filter(
            pk=1,
            authorized_teachers=teacher,
        ).exists()
    )
