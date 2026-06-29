import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()

from io import BytesIO
from PIL import Image as PILImage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.client import MULTIPART_CONTENT
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.contrib import admin
from main_app.models import GalleryCategory
from main_app.admin import GalleryCategoryAdmin

User = get_user_model()
User.objects.filter(username='admin_test_inline2').delete()
u = User.objects.create_superuser('admin_test_inline2', 'x@y.com', 'secret123')

img = BytesIO(); PILImage.new('RGB',(10,10),color='green').save(img,format='JPEG'); img.seek(0); cover = SimpleUploadedFile('cover.jpg', img.getvalue(), content_type='image/jpeg')
img2 = BytesIO(); PILImage.new('RGB',(10,10),color='red').save(img2,format='JPEG'); img2.seek(0); inline_image = SimpleUploadedFile('inline.jpg', img2.getvalue(), content_type='image/jpeg')

request = RequestFactory().post('/knu2026/main_app/gallerycategory/add/', {
    'name': 'test-category',
    'galleryimage_set-TOTAL_FORMS': '1',
    'galleryimage_set-INITIAL_FORMS': '0',
    'galleryimage_set-MIN_NUM_FORMS': '0',
    'galleryimage_set-MAX_NUM_FORMS': '1000',
    'galleryimage_set-0-caption': 'demo',
    'galleryimage_set-0-id': '',
    'galleryimage_set-0-DELETE': '',
}, files={'cover_image': cover, 'galleryimage_set-0-image': inline_image})
request.user = u
request._dont_enforce_csrf_checks = True

admin_obj = GalleryCategoryAdmin(GalleryCategory, admin.site)
inline = admin_obj.get_inline_instances(request)[0]
formset = inline.get_formset(request)(request.POST, request.FILES, instance=None, prefix='galleryimage_set')
print('formset forms', len(formset.forms))
for i, f in enumerate(formset.forms):
    print('form', i, 'is_bound', f.is_bound)
    print('form', i, 'files', f.files)
    print('form', i, 'data', f.data)
    print('form', i, 'errors', f.errors)
    print('form', i, 'image value', f['image'].value())
