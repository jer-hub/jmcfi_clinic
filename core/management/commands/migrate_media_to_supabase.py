"""Upload local media/ files to Supabase Storage (S3-compatible default storage)."""

from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Upload files from MEDIA_ROOT to the configured default storage "
        "(e.g. Supabase). Use --dry-run to preview without uploading."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List files that would be uploaded without writing to storage.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-upload even if the object key already exists in storage.",
        )

    def handle(self, *args, **options):
        if not getattr(settings, "USE_SUPABASE_STORAGE", False):
            raise CommandError(
                "USE_SUPABASE_STORAGE must be True and S3 credentials configured. "
                "See docs/SUPABASE.md."
            )

        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.is_dir():
            self.stdout.write(self.style.WARNING(f"No media directory at {media_root}"))
            return

        dry_run = options["dry_run"]
        force = options["force"]
        uploaded = 0
        skipped = 0
        errors = 0

        for path in sorted(media_root.rglob("*")):
            if not path.is_file():
                continue

            relative_key = path.relative_to(media_root).as_posix()

            if not force and default_storage.exists(relative_key):
                skipped += 1
                self.stdout.write(f"skip (exists): {relative_key}")
                continue

            if dry_run:
                self.stdout.write(f"would upload: {relative_key}")
                uploaded += 1
                continue

            try:
                with path.open("rb") as fh:
                    default_storage.save(relative_key, ContentFile(fh.read()))
                uploaded += 1
                self.stdout.write(self.style.SUCCESS(f"uploaded: {relative_key}"))
            except OSError as exc:
                errors += 1
                self.stderr.write(self.style.ERROR(f"failed {relative_key}: {exc}"))

        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(
            f"{prefix}done: {uploaded} uploaded, {skipped} skipped, {errors} errors"
        )
