import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()

from io import BytesIO
from PIL import Image as PILImage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.contrib import admin
from main_app.models import GalleryCategory
from main_app.admin import GalleryCategoryAdmin

User = get_user_model()
User.objects.filter(username='admin_test_debug').delete()
u = User.objects.create_superuser('admin_test_debug', 'x@y.com', 'secret123')

img = BytesIO()
PILImage.new('RGB', (10, 10), color='green').save(img, format='JPEG')
img.seek(0)
uploaded = SimpleUploadedFile('test.jpg', img.getvalue(), content_type='image/jpeg')

request = RequestFactory().post('/knu2026/main_app/gallerycategory/add/', {
    'name': 'test-category',
    'cover_image': uploaded,
    'galleryimage_set-TOTAL_FORMS': '1',
    'galleryimage_set-INITIAL_FORMS': '0',
    'galleryimage_set-MIN_NUM_FORMS': '0',
    'galleryimage_set-MAX_NUM_FORMS': '1000',
    'galleryimage_set-0-image': uploaded,
    'galleryimage_set-0-caption': 'demo',
})
request.user = u
request._dont_enforce_csrf_checks = True

admin_obj = GalleryCategoryAdmin(GalleryCategory, admin.site)
form_class = admin_obj.get_form(request)
form = form_class(data=request.POST, files=request.FILES)
print('form is_valid', form.is_valid())
print('form errors', form.errors)

for inline in admin_obj.get_inline_instances(request):
    formset = inline.get_formset(request)(request.POST, request.FILES, instance=None, prefix='galleryimage_set')
    print('inline', inline.__class__.__name__, 'is_valid', formset.is_valid())
    print('inline errors', formset.errors)
    for idx, f in enumerate(formset.forms):
        print('form', idx, 'errors', f.errors)
        print('form', idx, 'non_field_errors', f.non_field_errors())
