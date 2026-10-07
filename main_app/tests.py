import os
import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.shortcuts import render
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from core.compression import compress_image_field
from main_app.admin import LeadershipProfileForm
from main_app.models import CommitteeMember, EntryPopupImage, GalleryCategory, GalleryImage, LeadershipProfile, Notice


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


class CommitteePageTests(TestCase):
    def test_committee_page_shows_fixed_categories_and_member_details(self):
        CommitteeMember.objects.create(
            category='PRESIDENT',
            name='কমিটির সভাপতি',
            designation='সভাপতি',
            phone='01700000000',
            about='সভাপতি সম্পর্কে তথ্য',
        )

        response = self.client.get(reverse('committee_page'))

        self.assertEqual(response.status_code, 200)
        for _, category_name in CommitteeMember.CATEGORY_CHOICES:
            self.assertContains(response, category_name)
        self.assertContains(response, 'কমিটির সভাপতি')
        self.assertContains(response, '01700000000')
        self.assertContains(response, 'সভাপতি সম্পর্কে তথ্য')

    def test_committee_members_have_a_separate_admin_entry(self):
        user = get_user_model().objects.create_superuser('committee_admin', 'committee@example.com', 'secret123')
        self.client.force_login(user)

        response = self.client.get(reverse('admin:main_app_committeemember_add'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="category"')
        self.assertContains(response, 'name="name"')
        self.assertContains(response, 'name="designation"')
        self.assertContains(response, 'name="phone"')
        self.assertContains(response, 'name="about"')
        self.assertContains(response, 'name="image"')
        for _, category_name in CommitteeMember.CATEGORY_CHOICES:
            self.assertContains(response, category_name)

    def test_admin_can_upload_committee_member_photo_and_details(self):
        user = get_user_model().objects.create_superuser('committee_uploader', 'uploader@example.com', 'secret123')
        self.client.force_login(user)
        image_buffer = BytesIO()
        Image.new('RGB', (20, 20), color='blue').save(image_buffer, format='JPEG')
        uploaded_image = SimpleUploadedFile('member.jpg', image_buffer.getvalue(), content_type='image/jpeg')

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                response = self.client.post(
                    reverse('admin:main_app_committeemember_add'),
                    data={
                        'category': 'PRESIDENT',
                        'name': 'আপলোড করা সদস্য',
                        'designation': 'সভাপতি',
                        'phone': '01800000000',
                        'about': 'কমিটির সদস্যের পরিচিতি',
                        'order': '0',
                        'image': uploaded_image,
                    },
                    follow=True,
                )

                self.assertEqual(response.status_code, 200)
                member = CommitteeMember.objects.get(name='আপলোড করা সদস্য')
                self.assertEqual(member.phone, '01800000000')
                self.assertEqual(member.about, 'কমিটির সদস্যের পরিচিতি')
                self.assertTrue(member.image.storage.exists(member.image.name))


class LeadershipProfileFormTests(TestCase):
    def test_designation_defaults_from_profile_type_but_allows_override(self):
        image_buffer = BytesIO()
        Image.new('RGB', (20, 20), color='purple').save(image_buffer, format='JPEG')
        upload = SimpleUploadedFile('leader.jpg', image_buffer.getvalue(), content_type='image/jpeg')

        form = LeadershipProfileForm(
            data={
                'profile_type': 'HEADMASTER',
                'name': 'প্রধান শিক্ষক',
                'designation': '',
                'caption': 'শুভেচ্ছা',
            },
            files={'image': upload},
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['designation'], 'প্রধান শিক্ষক')

        override_form = LeadershipProfileForm(
            data={
                'profile_type': 'PRESIDENT',
                'name': 'সভাপতি',
                'designation': 'ব্যক্তিগত পদবি',
                'caption': 'সদয়',
            },
            files={'image': upload},
        )

        self.assertTrue(override_form.is_valid(), override_form.errors)
        self.assertEqual(override_form.cleaned_data['designation'], 'ব্যক্তিগত পদবি')


class NoticeLinkTests(TestCase):
    def setUp(self):
        media_directory = tempfile.TemporaryDirectory()
        self.addCleanup(media_directory.cleanup)
        media_settings = override_settings(MEDIA_ROOT=media_directory.name)
        media_settings.enable()
        self.addCleanup(media_settings.disable)

    def create_notice(self, **kwargs):
        title = kwargs.pop('title', 'গুরুত্বপূর্ণ নোটিশ')
        kwargs.setdefault('show_on_ticker', True)
        return Notice.objects.create(
            title=title,
            description='নোটিশের বিস্তারিত',
            file=SimpleUploadedFile('notice.pdf', b'%PDF-1.4 test notice'),
            **kwargs,
        )

    def test_ticker_notice_title_links_to_its_detail_page(self):
        notice = self.create_notice()

        response = self.client.get(reverse('all_notices'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'href="{reverse("notice_detail", args=[notice.pk])}">{notice.title}</a>',
        )

    def test_notice_detail_shows_download_link_and_file(self):
        notice = self.create_notice()

        response = self.client.get(reverse('notice_detail', args=[notice.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, notice.title)
        self.assertContains(response, notice.description)
        self.assertContains(
            response,
            f'href="{reverse("notice_download", args=[notice.pk])}"',
        )
        self.assertContains(response, notice.file.url)

    def test_notice_download_returns_file_as_attachment(self):
        notice = self.create_notice()

        response = self.client.get(reverse('notice_download', args=[notice.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('notice.pdf', response['Content-Disposition'])
        self.assertEqual(b''.join(response.streaming_content), b'%PDF-1.4 test notice')

    def test_inactive_notice_is_not_publicly_accessible(self):
        notice = self.create_notice(is_active=False)

        response = self.client.get(reverse('notice_detail', args=[notice.pk]))

        self.assertEqual(response.status_code, 404)

    def test_admin_can_select_new_notice_flag(self):
        user = get_user_model().objects.create_superuser('notice_admin', 'notice@example.com', 'secret123')
        self.client.force_login(user)

        response = self.client.get(reverse('admin:main_app_notice_add'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="is_new"')
        self.assertContains(response, 'নতুন নোটিশ?')

    def test_homepage_shows_new_badge_for_marked_dashboard_notices(self):
        self.create_notice(title='নতুন নোটিশ', show_on_dashboard=True, is_new=True, show_on_ticker=False)
        self.create_notice(title='সাধারণ নোটিশ', show_on_dashboard=True, is_new=False, show_on_ticker=False)
        self.create_notice(title='বোর্ডে দেখাবে না', show_on_dashboard=False, is_new=True, show_on_ticker=False)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'নতুন নোটিশ')
        self.assertContains(response, 'সাধারণ নোটিশ')
        self.assertNotContains(response, 'বোর্ডে দেখাবে না')
        self.assertEqual(response.content.decode().count('NEW</span>'), 1)

    def test_homepage_keeps_notice_board_compact_without_blank_space(self):
        for number in range(10):
            self.create_notice(
                title=f'বোর্ড নোটিশ {number + 1}',
                show_on_dashboard=True,
                show_on_ticker=False,
            )

        response = self.client.get(reverse('home'))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('notice-rows-viewport is-scrolling', content)
        self.assertLessEqual(content.count('class="notice-row notice-row-plain"'), 7)
        self.assertIn('.notice-table thead th:nth-child(2) { text-align: center; }', content)

    def test_seven_homepage_items_fit_without_scrolling(self):
        for number in range(7):
            self.create_notice(
                title=f'বোর্ড নোটিশ {number + 1}',
                show_on_dashboard=True,
                show_on_ticker=False,
            )

        response = self.client.get(reverse('home'))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('notice-rows-viewport is-scrolling', content)
        self.assertLessEqual(content.count('class="notice-row notice-row-plain"'), 7)


class WelcomeSliderTests(TestCase):
    def setUp(self):
        media_directory = tempfile.TemporaryDirectory()
        self.addCleanup(media_directory.cleanup)
        media_settings = override_settings(MEDIA_ROOT=media_directory.name)
        media_settings.enable()
        self.addCleanup(media_settings.disable)

    def make_image(self, name='welcome.jpg', color='purple'):
        image_buffer = BytesIO()
        Image.new('RGB', (40, 30), color=color).save(image_buffer, format='JPEG')
        return SimpleUploadedFile(name, image_buffer.getvalue(), content_type='image/jpeg')

    def test_homepage_only_includes_active_images_in_display_order(self):
        later = EntryPopupImage.objects.create(
            title='দ্বিতীয় ঘোষণা',
            image=self.make_image('second.jpg'),
            order=2,
        )
        inactive = EntryPopupImage.objects.create(
            title='নিষ্ক্রিয় ঘোষণা',
            image=self.make_image('inactive.jpg'),
            is_active=False,
            order=0,
        )
        first = EntryPopupImage.objects.create(
            title='প্রথম ঘোষণা',
            image=self.make_image('first.jpg'),
            order=1,
        )

        response = self.client.get(reverse('home'))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertLess(content.index(first.image.url), content.index(later.image.url))
        self.assertIn(first.image.url, content)
        self.assertIn(later.image.url, content)
        self.assertNotIn(inactive.image.url, content)

    def test_homepage_does_not_render_popup_without_active_images(self):
        EntryPopupImage.objects.create(
            title='নিষ্ক্রিয় ঘোষণা',
            image=self.make_image(),
            is_active=False,
        )

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="welcomeSlider"')

    def test_homepage_stays_available_when_an_uploaded_file_is_missing(self):
        image = EntryPopupImage.objects.create(image=self.make_image())
        image.image.storage.delete(image.image.name)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="welcomeSlider"')
        self.assertContains(response, image.image.url)

    def test_admin_has_a_separate_welcome_slider_and_image_preview(self):
        image = EntryPopupImage.objects.create(
            title='প্রবেশ বিজ্ঞপ্তি',
            image=self.make_image('notice.jpg'),
        )
        user = get_user_model().objects.create_superuser(
            'welcome_admin',
            'welcome@example.com',
            'secret123',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('admin:main_app_entrypopupimage_changelist'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Welcome Slider')
        self.assertContains(response, image.image.url)
        self.assertContains(response, 'notice.jpg')

    def test_admin_rejects_invalid_image_upload(self):
        user = get_user_model().objects.create_superuser(
            'welcome_upload_admin',
            'welcome-upload@example.com',
            'secret123',
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse('admin:main_app_entrypopupimage_add'),
            data={
                'title': 'ভুল ফাইল',
                'is_active': 'on',
                'order': '0',
                'image': SimpleUploadedFile(
                    'not-an-image.jpg',
                    b'invalid image data',
                    content_type='image/jpeg',
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(EntryPopupImage.objects.filter(title='ভুল ফাইল').exists())
        self.assertContains(response, 'Upload a valid image')