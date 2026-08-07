import os
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


def drive_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    owner_id = instance.owner_id or 'unknown'
    return f'drive/{owner_id}/{uuid.uuid4().hex}{ext}'


class DriveItem(models.Model):
    class Kind(models.TextChoices):
        FOLDER = 'folder', 'Folder'
        FILE = 'file', 'File'

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='drive_items',
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        limit_choices_to={'kind': Kind.FOLDER},
    )
    kind = models.CharField(max_length=10, choices=Kind.choices)
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to=drive_upload_to, blank=True, null=True)
    content_type = models.CharField(max_length=128, blank=True, default='')
    size_bytes = models.PositiveBigIntegerField(default=0)
    trashed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['kind', 'name']
        indexes = [
            models.Index(fields=['parent', 'trashed_at']),
            models.Index(fields=['owner', 'name']),
            models.Index(fields=['name']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['parent', 'name'],
                condition=Q(trashed_at__isnull=True),
                name='unique_drive_name_per_parent_active',
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def is_folder(self):
        return self.kind == self.Kind.FOLDER

    @property
    def is_file(self):
        return self.kind == self.Kind.FILE

    @property
    def is_trashed(self):
        return self.trashed_at is not None

    def soft_delete(self):
        self.trashed_at = timezone.now()
        self.save(update_fields=['trashed_at', 'updated_at'])

    def restore(self):
        self.trashed_at = None
        self.save(update_fields=['trashed_at', 'updated_at'])
