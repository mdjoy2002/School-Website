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
User.objects.filter(username='admin_test_inline').delete()
u = User.objects.create_superuser('admin_test_inline', 'x@y.com', 'secret123')

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
})
request.user = u
request._dont_enforce_csrf_checks = True
request.FILES = {'cover_image': cover, 'galleryimage_set-0-image': inline_image}

admin_obj = GalleryCategoryAdmin(GalleryCategory, admin.site)
form = admin_obj.get_form(request)(data=request.POST, files=request.FILES)
print('main valid', form.is_valid())
print('main errors', form.errors)

inline = admin_obj.get_inline_instances(request)[0]
formset = inline.get_formset(request)(request.POST, request.FILES, instance=None, prefix='galleryimage_set')
print('inline valid', formset.is_valid())
print('inline errors', formset.errors)
for i, f in enumerate(formset.forms):
    print('form', i, 'errors', f.errors)
    print('form', i, 'cleaned', f.cleaned_data)
