"""Clinic Files (Drive) business logic: validation, uniqueness, move cycles."""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from .models import DriveItem

MAX_UPLOAD_BYTES = 50 * 1024 * 1024

ALLOWED_EXTENSIONS = frozenset({
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.txt', '.csv', '.rtf', '.odt', '.ods',
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg',
    '.zip', '.7z', '.rar',
    '.mp3', '.mp4', '.wav', '.webm',
})

ALLOWED_CONTENT_TYPES = frozenset({
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'text/plain',
    'text/csv',
    'application/rtf',
    'application/vnd.oasis.opendocument.text',
    'application/vnd.oasis.opendocument.spreadsheet',
    'image/jpeg',
    'image/png',
    'image/gif',
    'image/webp',
    'image/bmp',
    'image/svg+xml',
    'application/zip',
    'application/x-7z-compressed',
    'application/x-rar-compressed',
    'application/octet-stream',  # allowed only with known extension
    'audio/mpeg',
    'audio/wav',
    'video/mp4',
    'video/webm',
})


def active_siblings_qs(parent, *, exclude_pk=None):
    qs = DriveItem.objects.filter(trashed_at__isnull=True, parent=parent)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs


def name_taken(parent, name: str, *, exclude_pk=None) -> bool:
    return active_siblings_qs(parent, exclude_pk=exclude_pk).filter(name__iexact=name.strip()).exists()


def ensure_unique_name(parent, name: str, *, exclude_pk=None):
    cleaned = (name or '').strip()
    if not cleaned:
        raise ValidationError('Name is required.')
    if len(cleaned) > 255:
        raise ValidationError('Name is too long.')
    if name_taken(parent, cleaned, exclude_pk=exclude_pk):
        raise ValidationError(f'An item named "{cleaned}" already exists here.')
    return cleaned


def breadcrumbs_for(folder: DriveItem | None) -> list[DriveItem]:
    if folder is None:
        return []
    chain = []
    current = folder
    seen = set()
    while current is not None:
        if current.pk in seen:
            break
        seen.add(current.pk)
        chain.append(current)
        current = current.parent
    chain.reverse()
    return chain


def is_descendant(ancestor: DriveItem, candidate_parent: DriveItem | None) -> bool:
    """True if candidate_parent is ancestor itself or inside ancestor's subtree."""
    if candidate_parent is None:
        return False
    if candidate_parent.pk == ancestor.pk:
        return True
    current = candidate_parent
    seen = set()
    while current is not None:
        if current.pk in seen:
            return True
        if current.pk == ancestor.pk:
            return True
        seen.add(current.pk)
        current = current.parent
    return False


def validate_upload(uploaded_file):
    if uploaded_file is None:
        raise ValidationError('No file provided.')
    if uploaded_file.size > MAX_UPLOAD_BYTES:
        raise ValidationError('File too large. Maximum size is 50MB.')

    name = getattr(uploaded_file, 'name', '') or 'upload'
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(f'File type "{ext or "unknown"}" is not allowed.')

    content_type = (getattr(uploaded_file, 'content_type', None) or '').lower()
    if not content_type:
        guessed, _ = mimetypes.guess_type(name)
        content_type = (guessed or 'application/octet-stream').lower()

    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValidationError(f'Content type "{content_type}" is not allowed.')

    if content_type == 'application/octet-stream' and ext not in ALLOWED_EXTENSIONS:
        raise ValidationError('Unrecognized binary file type.')

    display_name = os.path.basename(name).strip() or f'upload{ext}'
    return display_name, content_type


def create_folder(*, owner, parent, name: str) -> DriveItem:
    if parent is not None and (parent.is_file or parent.is_trashed):
        raise ValidationError('Invalid parent folder.')
    cleaned = ensure_unique_name(parent, name)
    return DriveItem.objects.create(
        owner=owner,
        parent=parent,
        kind=DriveItem.Kind.FOLDER,
        name=cleaned,
    )


def create_file(*, owner, parent, uploaded_file) -> DriveItem:
    if parent is not None and (parent.is_file or parent.is_trashed):
        raise ValidationError('Invalid parent folder.')
    display_name, content_type = validate_upload(uploaded_file)
    cleaned = ensure_unique_name(parent, display_name)
    item = DriveItem(
        owner=owner,
        parent=parent,
        kind=DriveItem.Kind.FILE,
        name=cleaned,
        content_type=content_type,
        size_bytes=uploaded_file.size,
    )
    item.file = uploaded_file
    item.save()
    return item


def rename_item(item: DriveItem, new_name: str) -> DriveItem:
    cleaned = ensure_unique_name(item.parent, new_name, exclude_pk=item.pk)
    item.name = cleaned
    item.save(update_fields=['name', 'updated_at'])
    return item


def move_item(item: DriveItem, new_parent: DriveItem | None) -> DriveItem:
    if new_parent is not None:
        if new_parent.is_file or new_parent.is_trashed:
            raise ValidationError('Invalid destination folder.')
        if item.is_folder and is_descendant(item, new_parent):
            raise ValidationError('Cannot move a folder into itself or a subfolder.')
    cleaned = ensure_unique_name(new_parent, item.name, exclude_pk=item.pk)
    item.parent = new_parent
    item.name = cleaned
    item.save(update_fields=['parent', 'name', 'updated_at'])
    return item


def trash_item(item: DriveItem) -> DriveItem:
    if item.is_trashed:
        return item
    # Soft-delete descendants for folders so they leave the active tree.
    if item.is_folder:
        _trash_subtree(item)
    else:
        item.soft_delete()
    return item


def trash_items(item_ids) -> int:
    trashed = 0
    qs = DriveItem.objects.filter(pk__in=item_ids, trashed_at__isnull=True).order_by('-kind', 'name')
    for item in qs:
        try:
            current = DriveItem.objects.get(pk=item.pk, trashed_at__isnull=True)
        except DriveItem.DoesNotExist:
            continue
        trash_item(current)
        trashed += 1
    return trashed


def _trash_subtree(folder: DriveItem):
    now = timezone.now()
    stack = [folder]
    ids = []
    while stack:
        current = stack.pop()
        ids.append(current.pk)
        stack.extend(
            list(
                DriveItem.objects.filter(
                    parent=current,
                    trashed_at__isnull=True,
                )
            )
        )
    DriveItem.objects.filter(pk__in=ids, trashed_at__isnull=True).update(
        trashed_at=now,
        updated_at=now,
    )


def restore_item(item: DriveItem) -> DriveItem:
    if not item.is_trashed:
        return item
    parent = item.parent
    if parent is not None and parent.is_trashed:
        parent = None

    target_name = item.name
    if name_taken(parent, target_name, exclude_pk=item.pk):
        parent = None
        base = item.name
        n = 1
        candidate = base
        while name_taken(None, candidate, exclude_pk=item.pk):
            n += 1
            candidate = f'{base} ({n})'
        target_name = candidate

    item.parent = parent
    item.name = target_name
    item.trashed_at = None
    item.save(update_fields=['parent', 'name', 'trashed_at', 'updated_at'])
    return item


def purge_item(item: DriveItem):
    """Permanently delete item and storage; cascades children via FK."""
    if item.is_file and item.file:
        item.file.delete(save=False)
    # For folders, delete child file blobs first
    if item.is_folder:
        for child in DriveItem.objects.filter(parent=item).iterator():
            if child.is_file and child.file:
                child.file.delete(save=False)
    item.delete()


def restore_items(item_ids) -> tuple[int, list[str]]:
    restored = 0
    errors: list[str] = []
    qs = DriveItem.objects.filter(pk__in=item_ids, trashed_at__isnull=False).order_by('kind', 'name')
    for item in qs:
        try:
            restore_item(item)
            restored += 1
        except ValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') else str(exc)
            errors.append(msg or f'Could not restore {item.name}.')
    return restored, errors


def purge_items(item_ids) -> int:
    purged = 0
    qs = list(DriveItem.objects.filter(pk__in=item_ids, trashed_at__isnull=False).order_by('-kind', 'name'))
    for item in qs:
        try:
            current = DriveItem.objects.get(pk=item.pk, trashed_at__isnull=False)
        except DriveItem.DoesNotExist:
            continue
        purge_item(current)
        purged += 1
    return purged


def empty_trash() -> int:
    """Permanently delete every trashed item (purge trash roots; children cascade)."""
    roots = DriveItem.objects.filter(trashed_at__isnull=False).filter(
        Q(parent__isnull=True) | Q(parent__trashed_at__isnull=True)
    )
    return purge_items(list(roots.values_list('pk', flat=True)))


def list_active_children(parent: DriveItem | None):
    return (
        DriveItem.objects.filter(parent=parent, trashed_at__isnull=True)
        .select_related('owner', 'parent')
        .order_by('kind', 'name')
    )


def search_active(query: str):
    q = (query or '').strip()
    qs = DriveItem.objects.filter(trashed_at__isnull=True).select_related('owner', 'parent')
    if q:
        qs = qs.filter(name__icontains=q)
    return qs.order_by('kind', 'name')


def list_trashed():
    return (
        DriveItem.objects.filter(trashed_at__isnull=False)
        .select_related('owner', 'parent')
        .order_by('-trashed_at', 'name')
    )


def get_active_folder(pk) -> DriveItem | None:
    if not pk:
        return None
    return DriveItem.objects.filter(
        pk=pk,
        kind=DriveItem.Kind.FOLDER,
        trashed_at__isnull=True,
    ).first()


def folder_options_excluding(item: DriveItem | None = None):
    """Folders available as move targets (active only), excluding item subtree."""
    qs = DriveItem.objects.filter(
        kind=DriveItem.Kind.FOLDER,
        trashed_at__isnull=True,
    ).order_by('name')
    if item is None or not item.is_folder:
        return qs
    excluded = set()
    stack = [item]
    while stack:
        current = stack.pop()
        excluded.add(current.pk)
        stack.extend(list(DriveItem.objects.filter(parent=current, kind=DriveItem.Kind.FOLDER)))
    return qs.exclude(pk__in=excluded)
