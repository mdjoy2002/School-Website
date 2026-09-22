import os
from io import BytesIO
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.contrib.auth import get_user_model
from django.urls import reverse
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from main_app.admin import GalleryCategoryAdmin
from main_app.models import GalleryCategory, GalleryImage

orig = GalleryCategoryAdmin.save_model

def patched(self, request, obj, form, change):
    print('save_model called')
    print('form valid', form.is_valid())
    print('cleaned_data keys', list(getattr(form, 'cleaned_data', {}).keys()))
    print('request files names', list(getattr(request, 'FILES', {}).keys()))
    if hasattr(request, 'FILES'):
        print('request files list', request.FILES.lists())
    return orig(self, request, obj, form, change)

GalleryCategoryAdmin.save_model = patched

user = get_user_model().objects.create_superuser('dbg2','dbg2@example.com','secret123')
c = Client()
c.force_login(user)
cover = BytesIO(); Image.new('RGB',(20,20),color='green').save(cover,format='JPEG'); cover.seek(0)
img = BytesIO(); Image.new('RGB',(20,20),color='red').save(img,format='JPEG'); img.seek(0)
resp = c.post(reverse('admin:main_app_gallerycategory_add'), {'name':'DebugPatched'}, files={'cover_image':SimpleUploadedFile('cover.jpg',cover.getvalue(),content_type='image/jpeg'),'gallery_images':SimpleUploadedFile('gallery-1.jpg',img.getvalue(),content_type='image/jpeg')}, follow=True)
print('status', resp.status_code)
category = GalleryCategory.objects.filter(name='DebugPatched').first()
print('category', category)
print('images count', GalleryImage.objects.filter(category=category).count())
