import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()

from io import BytesIO
from PIL import Image as PILImage
from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from main_app.models import GalleryImage

img = BytesIO()
PILImage.new('RGB', (10, 10), color='green').save(img, format='JPEG')
img.seek(0)
file_obj = SimpleUploadedFile('inline.jpg', img.getvalue(), content_type='image/jpeg')

class GalleryImageForm(forms.ModelForm):
    class Meta:
        model = GalleryImage
        fields = ['image', 'caption', 'category']

form = GalleryImageForm(data={'caption': 'demo', 'category': '1'}, files={'image': file_obj})
print('is_valid', form.is_valid())
print('errors', form.errors)
print('cleaned', form.cleaned_data if form.is_valid() else None)
