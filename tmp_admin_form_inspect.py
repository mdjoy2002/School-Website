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
User.objects.filter(username='gallery_admin_form_inspect').delete()
u = User.objects.create_superuser('gallery_admin_form_inspect', 'gallery@example.com', 'secret123')

request = RequestFactory().get('/knu2026/main_app/gallerycategory/add/')
request.user = u
admin_obj = GalleryCategoryAdmin(GalleryCategory, admin.site)
form = admin_obj.get_form(request)()
print('fields', form.fields.keys())
for name, field in form.fields.items():
    print(name, type(field).__name__, field.required)
