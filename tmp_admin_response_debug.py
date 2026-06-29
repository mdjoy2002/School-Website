import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()

from io import BytesIO
from PIL import Image as PILImage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.contrib.auth import get_user_model
from main_app.models import GalleryCategory, GalleryImage

User = get_user_model()
User.objects.filter(username='admin_test_resp').delete()
u = User.objects.create_superuser('admin_test_resp', 'x@y.com', 'secret123')

c = Client()
c.force_login(u)

cover_bytes = BytesIO(); PILImage.new('RGB', (10, 10), color='green').save(cover_bytes, format='JPEG'); cover_bytes.seek(0)
cover = SimpleUploadedFile('cover.jpg', cover_bytes.getvalue(), content_type='image/jpeg')

inline_bytes = BytesIO(); PILImage.new('RGB', (10, 10), color='red').save(inline_bytes, format='JPEG'); inline_bytes.seek(0)
inline_image = SimpleUploadedFile('inline.jpg', inline_bytes.getvalue(), content_type='image/jpeg')

payload = {
    'name': 'response-category',
    'galleryimage_set-TOTAL_FORMS': '1',
    'galleryimage_set-INITIAL_FORMS': '0',
    'galleryimage_set-MIN_NUM_FORMS': '0',
    'galleryimage_set-MAX_NUM_FORMS': '1000',
    'galleryimage_set-0-caption': 'demo',
}
files = {
    'cover_image': cover,
    'galleryimage_set-0-image': inline_image,
}

response = c.post('/knu2026/main_app/gallerycategory/add/', data=payload, files=files, follow=True)
print('status', response.status_code)
print('redirect_chain', response.redirect_chain)
print('context is none?', response.context is None)
if response.context is not None:
    print('context keys', list(response.context.keys())[:20])
    print('adminform', response.context.get('adminform'))
    print('adminform form errors', response.context.get('adminform').form.errors if response.context.get('adminform') else None)
    for idx, formset_wrapper in enumerate(response.context.get('inline_admin_formsets', [])):
        print('inline formset', idx, 'errors', formset_wrapper.formset.errors)
        for form in formset_wrapper.formset.forms:
            print('form errors', form.errors)
print('category_count', GalleryCategory.objects.filter(name='response-category').count())
print('image_count', GalleryImage.objects.filter(caption='demo').count())
