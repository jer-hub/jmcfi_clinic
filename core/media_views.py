"""Serve private Supabase (or default) storage files to authenticated users."""

import mimetypes

from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404

from core.private_storage_acl import can_access_private_path


@login_required
def private_storage_serve(request, path):
    """
    Stream a private upload for logged-in users who pass path ACL.

    Supabase S3 presigned URLs are not browser-safe; Django proxies reads instead.
    """
    path = (path or "").strip().lstrip("/")
    if not path or ".." in path.split("/"):
        raise Http404

    if not can_access_private_path(request.user, path):
        raise Http404

    if not default_storage.exists(path):
        raise Http404

    content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    return FileResponse(default_storage.open(path, "rb"), content_type=content_type)
