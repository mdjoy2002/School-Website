from io import BytesIO

from django.core.files.base import ContentFile
from django.db import models
from PIL import Image, UnidentifiedImageError

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None


def compress_image_field(file_field, quality=85):
    """Compress image files for ImageField uploads."""
    if not file_field or not getattr(file_field, 'name', None):
        return

    try:
        file_field.open('rb')
        file_field.seek(0)
        image = Image.open(file_field)
    except (UnidentifiedImageError, OSError):
        return
    finally:
        try:
            file_field.close()
        except Exception:
            pass

    original_size = getattr(file_field, 'size', None)
    image_format = image.format or 'JPEG'
    if image_format.upper() in ('JPEG', 'JPG'):
        if image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')
        save_kwargs = {'format': 'JPEG', 'quality': quality, 'optimize': True, 'progressive': True}
    elif image_format.upper() == 'PNG':
        save_kwargs = {'format': 'PNG', 'optimize': True, 'compress_level': 6}
    else:
        save_kwargs = {'format': image_format}

    output = BytesIO()
    try:
        image.save(output, **save_kwargs)
    except OSError:
        return

    if original_size is not None and output.tell() >= original_size:
        return

    output.seek(0)
    content = ContentFile(output.read())
    file_field.save(file_field.name, content, save=False)


def compress_pdf_field(file_field):
    """Attempt to compress uploaded PDF files by rewriting them."""
    if PyPDF2 is None or not file_field or not getattr(file_field, 'name', None):
        return

    try:
        file_field.open('rb')
        reader = PyPDF2.PdfReader(file_field)
    except Exception:
        return
    finally:
        try:
            file_field.close()
        except Exception:
            pass

    writer = PyPDF2.PdfWriter()
    if hasattr(writer, 'compress_content_streams'):
        writer.compress_content_streams = True

    for page in reader.pages:
        writer.add_page(page)

    try:
        metadata = reader.metadata
        if metadata is not None:
            writer.add_metadata(metadata)
    except Exception:
        pass

    output = BytesIO()
    try:
        writer.write(output)
    except Exception:
        return

    original_size = getattr(file_field, 'size', None)
    if original_size is not None and output.tell() >= original_size:
        return

    output.seek(0)
    content = ContentFile(output.read())
    file_field.save(file_field.name, content, save=False)


class CompressedUploadMixin(models.Model):
    class Meta:
        abstract = True

    IMAGE_FIELDS = []
    PDF_FIELDS = []

    def save(self, *args, **kwargs):
        for field_name in getattr(self, 'IMAGE_FIELDS', []):
            compress_image_field(getattr(self, field_name, None))

        for field_name in getattr(self, 'PDF_FIELDS', []):
            compress_pdf_field(getattr(self, field_name, None))

        super().save(*args, **kwargs)
