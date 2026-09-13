"""Shared upload validation helpers (images and related)."""

from __future__ import annotations

import io
import mimetypes
from pathlib import Path

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

IMAGE_EXTENSIONS = frozenset({'.jpg', '.jpeg', '.png', '.gif', '.webp'})
IMAGE_CONTENT_TYPES = frozenset({
    'image/jpeg',
    'image/png',
    'image/gif',
    'image/webp',
})

# Pillow format name → preferred extension
_FORMAT_TO_EXT = {
    'JPEG': '.jpg',
    'PNG': '.png',
    'GIF': '.gif',
    'WEBP': '.webp',
}


def verify_image_upload(uploaded_file, *, max_bytes: int = 5 * 1024 * 1024):
    """
    Validate an image upload by extension, declared MIME, size, and Pillow verify.

    Returns (safe_extension, content_type).
    """
    if uploaded_file is None:
        raise ValidationError('No file provided.')
    if uploaded_file.size > max_bytes:
        raise ValidationError(f'File too large. Maximum size is {max_bytes // (1024 * 1024)}MB.')

    name = getattr(uploaded_file, 'name', '') or 'upload'
    ext = Path(name).suffix.lower()
    if ext == '.jpeg':
        ext = '.jpg'
    if ext not in IMAGE_EXTENSIONS:
        raise ValidationError(f'File type "{ext or "unknown"}" is not allowed.')

    content_type = (getattr(uploaded_file, 'content_type', None) or '').lower()
    if not content_type:
        guessed, _ = mimetypes.guess_type(name)
        content_type = (guessed or '').lower()
    if content_type == 'image/jpg':
        content_type = 'image/jpeg'
    if content_type not in IMAGE_CONTENT_TYPES:
        raise ValidationError(f'Content type "{content_type or "unknown"}" is not allowed.')

    try:
        uploaded_file.seek(0)
        raw = uploaded_file.read()
        uploaded_file.seek(0)
        with Image.open(io.BytesIO(raw)) as img:
            img.verify()
            format_name = (img.format or '').upper()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationError('File is not a valid image.') from exc

    if format_name not in _FORMAT_TO_EXT:
        raise ValidationError('Unsupported image format.')

    safe_ext = _FORMAT_TO_EXT[format_name]
    # Re-open after verify() which closes the image
    uploaded_file.seek(0)
    return safe_ext, content_type
