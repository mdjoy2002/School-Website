import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()

from io import BytesIO
from PIL import Image as PILImage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from main_app.models import GalleryCategory, GalleryImage

User = get_user_model()
User.objects.filter(username='gallery_admin_hook_debug').delete()
u = User.objects.create_superuser('gallery_admin_hook_debug', 'gallery@example.com', 'secret123')

c = Client()
c.force_login(u)

cover = BytesIO(); PILImage.new('RGB',(20,20),color='green').save(cover,format='JPEG'); cover.seek(0)
inline = BytesIO(); PILImage.new('RGB',(20,20),color='red').save(inline,format='JPEG'); inline.seek(0)

response = c.post(
    reverse('admin:main_app_gallerycategory_add'),
    data={'name':'Summer Fair'},
    files={'cover_image': SimpleUploadedFile('cover.jpg', cover.getvalue(), content_type='image/jpeg'), 'gallery_images': [SimpleUploadedFile('gallery-1.jpg', inline.getvalue(), content_type='image/jpeg')]},
    follow=True,
)

print('status', response.status_code)
print('categories', GalleryCategory.objects.filter(name='Summer Fair').count())
print('images', GalleryImage.objects.filter(caption='').count())
