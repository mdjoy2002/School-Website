import os
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.shortcuts import render
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from PIL import Image

from core.compression import compress_image_field
from main_app.models import GalleryCategory, GalleryImage


def home(request):
    return render(request, 'index.html')


class CompressionTests(SimpleTestCase):
    def test_compress_image_field_does_not_fail_on_uploaded_image(self):
        image = Image.new('RGB', (20, 20), color='red')
        buffer = BytesIO()
        image.save(buffer, format='JPEG')

        uploaded_file = SimpleUploadedFile(
            'test.jpg',
            buffer.getvalue(),
            content_type='image/jpeg'
        )

        compress_image_field(uploaded_file)

        self.assertTrue(uploaded_file.name)


class MediaServingTests(SimpleTestCase):
    def test_media_files_are_served_from_media_root(self):
        media_root = os.path.join(os.getcwd(), 'media')
        media_path = os.path.join(media_root, 'gallery', 'photos')
        os.makedirs(media_path, exist_ok=True)
        image_path = os.path.join(media_path, 'example.jpg')
        with open(image_path, 'wb') as fh:
            fh.write(b'fake-image-data')

        try:
            response = self.client.get('/media/gallery/photos/example.jpg')
        finally:
            if os.path.exists(image_path):
                try:
                    os.remove(image_path)
                except PermissionError:
                    pass

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), b'fake-image-data')


class GalleryAdminTests(TestCase):
    def test_admin_can_save_gallery_category_with_uploaded_images(self):
        user = get_user_model().objects.create_superuser('gallery_admin', 'gallery@example.com', 'secret123')
        self.client.force_login(user)

        cover_image = BytesIO()
        Image.new('RGB', (20, 20), color='green').save(cover_image, format='JPEG')
        cover_image.seek(0)

        inline_image = BytesIO()
        Image.new('RGB', (20, 20), color='red').save(inline_image, format='JPEG')
        inline_image.seek(0)

        response = self.client.post(
            reverse('admin:main_app_gallerycategory_add'),
            data={'name': 'Summer Fair'},
            files={
                'cover_image': SimpleUploadedFile('cover.jpg', cover_image.getvalue(), content_type='image/jpeg'),
                'gallery_images': SimpleUploadedFile('gallery-1.jpg', inline_image.getvalue(), content_type='image/jpeg'),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        category = GalleryCategory.objects.filter(name='Summer Fair').first()
        self.assertIsNotNone(category)
        self.assertTrue(GalleryImage.objects.filter(category=category).exists())