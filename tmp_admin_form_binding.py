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
User.objects.filter(username='gallery_admin_form_binding').delete()
u = User.objects.create_superuser('gallery_admin_form_binding', 'gallery@example.com', 'secret123')

cover = BytesIO(); PILImage.new('RGB',(20,20),color='green').save(cover,format='JPEG'); cover.seek(0)
inline = BytesIO(); PILImage.new('RGB',(20,20),color='red').save(inline,format='JPEG'); inline.seek(0)

request = RequestFactory().post('/knu2026/main_app/gallerycategory/add/', data={'name':'Summer Fair'}, files={'cover_image': SimpleUploadedFile('cover.jpg', cover.getvalue(), content_type='image/jpeg'), 'gallery_images': [SimpleUploadedFile('gallery-1.jpg', inline.getvalue(), content_type='image/jpeg')]})
request.user = u
request._dont_enforce_csrf_checks = True
admin_obj = GalleryCategoryAdmin(GalleryCategory, admin.site)
form = admin_obj.get_form(request)(data=request.POST, files=request.FILES)
print('valid', form.is_valid())
print('errors', form.errors)
print('files keys', list(request.FILES.keys()))
print('gallery_images', request.FILES.getlist('gallery_images'))
print('cleaned', form.cleaned_data)
