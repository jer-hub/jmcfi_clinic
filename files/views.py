from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from core.decorators import role_required
from core.doctor_access import MODULE_FILES, has_clinical_module
from core.htmx_utils import is_htmx_request

from .models import DriveItem
from . import services

_ACCESS_ROLES = ('staff', 'doctor')
VIEW_COOKIE = 'files_view_mode'


def _deny_without_module(request):
    from core.access_control import AccessReason, access_denied_response

    if has_clinical_module(request.user, MODULE_FILES):
        return None
    return access_denied_response(
        request,
        status_code=403,
        reason=AccessReason.FORBIDDEN,
    )


def _view_mode(request) -> str:
    mode = request.GET.get('view') or request.COOKIES.get(VIEW_COOKIE) or 'list'
    return mode if mode in ('list', 'grid') else 'list'


def _resolve_parent(parent_id):
    if not parent_id:
        return None
    folder = services.get_active_folder(parent_id)
    if folder is None:
        raise ValidationError('Folder not found.')
    return folder


def _browse_redirect(parent=None):
    if parent is None:
        return redirect('files:browse')
    return redirect(f"{reverse('files:browse')}?folder={parent.pk}")


def _wants_json(request) -> bool:
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return True
    accept = (request.headers.get('Accept') or '').lower()
    return 'application/json' in accept


def _browse_url(parent=None) -> str:
    if parent is None:
        return reverse('files:browse')
    return f"{reverse('files:browse')}?folder={parent.pk}"


def _render_browse(request, *, folder, items, extra=None):
    ctx = {
        'folder': folder,
        'items': items,
        'breadcrumbs': services.breadcrumbs_for(folder),
        'view_mode': _view_mode(request),
        'folder_options': services.folder_options_excluding(),
        'page_title': folder.name if folder else 'My Drive',
    }
    if extra:
        ctx.update(extra)
    template = (
        'files/partials/_drive_pane.html'
        if is_htmx_request(request)
        else 'files/browse.html'
    )
    response = render(request, template, ctx)
    response.set_cookie(VIEW_COOKIE, ctx['view_mode'], max_age=60 * 60 * 24 * 365)
    return response


@login_required
@role_required(*_ACCESS_ROLES)
@require_GET
def drive_browse(request):
    denied = _deny_without_module(request)
    if denied:
        return denied

    folder_id = request.GET.get('folder')
    folder = None
    if folder_id:
        folder = services.get_active_folder(folder_id)
        if folder is None:
            messages.error(request, 'Folder not found.')
            return redirect('files:browse')

    items = services.list_active_children(folder)
    return _render_browse(request, folder=folder, items=items)


@login_required
@role_required(*_ACCESS_ROLES)
@require_GET
def drive_trash(request):
    denied = _deny_without_module(request)
    if denied:
        return denied

    items = services.list_trashed()
    ctx = {
        'items': items,
        'view_mode': _view_mode(request),
        'page_title': 'Trash',
        'is_trash': True,
    }
    template = (
        'files/partials/_trash_pane.html'
        if is_htmx_request(request)
        else 'files/trash.html'
    )
    response = render(request, template, ctx)
    response.set_cookie(VIEW_COOKIE, ctx['view_mode'], max_age=60 * 60 * 24 * 365)
    return response


@login_required
@role_required(*_ACCESS_ROLES)
@require_GET
def drive_search(request):
    denied = _deny_without_module(request)
    if denied:
        return denied

    q = request.GET.get('q', '')
    has_query = bool(q.strip())
    items = services.search_active(q) if has_query else DriveItem.objects.none()
    ctx = {
        'items': items,
        'search_query': q,
        'has_search_query': has_query,
        'view_mode': _view_mode(request),
        'page_title': 'Search',
        'folder_options': services.folder_options_excluding(),
        'is_search': True,
    }
    template = (
        'files/partials/_drive_pane.html'
        if is_htmx_request(request)
        else 'files/search.html'
    )
    response = render(request, template, ctx)
    response.set_cookie(VIEW_COOKIE, ctx['view_mode'], max_age=60 * 60 * 24 * 365)
    return response


@login_required
@role_required(*_ACCESS_ROLES)
@require_POST
def folder_create(request):
    denied = _deny_without_module(request)
    if denied:
        return denied

    parent_id = request.POST.get('parent_id') or None
    parent = None
    try:
        parent = _resolve_parent(int(parent_id) if parent_id else None)
        services.create_folder(owner=request.user, parent=parent, name=request.POST.get('name', ''))
        messages.success(request, 'Folder created.')
    except (ValidationError, ValueError, TypeError) as exc:
        msg = exc.messages[0] if hasattr(exc, 'messages') else str(exc)
        messages.error(request, msg or 'Could not create folder.')
        if parent_id and parent is None:
            parent = services.get_active_folder(parent_id)
    return _browse_redirect(parent)


@login_required
@role_required(*_ACCESS_ROLES)
@require_POST
def drive_upload(request):
    denied = _deny_without_module(request)
    if denied:
        return denied

    parent_id = request.POST.get('parent_id') or None
    parent = None
    created = 0
    errors = []
    fatal = None
    try:
        parent = _resolve_parent(int(parent_id) if parent_id else None)
        uploads = request.FILES.getlist('files')
        if not uploads:
            raise ValidationError('Select at least one file to upload.')
        for uploaded in uploads:
            try:
                services.create_file(owner=request.user, parent=parent, uploaded_file=uploaded)
                created += 1
            except ValidationError as exc:
                errors.append(exc.messages[0] if hasattr(exc, 'messages') else str(exc))
        if created and not _wants_json(request):
            messages.success(request, f'Uploaded {created} file{"s" if created != 1 else ""}.')
        if not _wants_json(request):
            for err in errors[:5]:
                messages.error(request, err)
    except (ValidationError, ValueError, TypeError) as exc:
        fatal = exc.messages[0] if hasattr(exc, 'messages') else str(exc)
        fatal = fatal or 'Upload failed.'
        if not _wants_json(request):
            messages.error(request, fatal)
        if parent_id and parent is None:
            parent = services.get_active_folder(parent_id)

    if _wants_json(request):
        if fatal:
            errors = [fatal] + errors
        return JsonResponse(
            {
                'ok': created > 0 and not fatal,
                'created': created,
                'errors': errors[:5],
                'folder_id': parent.pk if parent else None,
                'browse_url': _browse_url(parent),
                'message': (
                    f'Uploaded {created} file{"s" if created != 1 else ""}.'
                    if created
                    else ''
                ),
            },
            status=200 if created or not fatal else 400,
        )
    return _browse_redirect(parent)


@login_required
@role_required(*_ACCESS_ROLES)
@require_GET
def drive_download(request, pk):
    denied = _deny_without_module(request)
    if denied:
        return denied

    item = get_object_or_404(DriveItem, pk=pk)
    if item.is_folder:
        raise Http404('Folders cannot be downloaded.')
    if not item.file:
        raise Http404('File missing.')
    # Allow download from trash (recover before purge)
    handle = item.file.open('rb')
    response = FileResponse(handle, as_attachment=True, filename=item.name)
    if item.content_type:
        response['Content-Type'] = item.content_type
    return response


@login_required
@role_required(*_ACCESS_ROLES)
@require_POST
def item_rename(request, pk):
    denied = _deny_without_module(request)
    if denied:
        return denied

    item = get_object_or_404(DriveItem, pk=pk)
    try:
        services.rename_item(item, request.POST.get('name', ''))
        messages.success(request, 'Renamed.')
    except ValidationError as exc:
        messages.error(request, exc.messages[0] if hasattr(exc, 'messages') else str(exc))
    if item.is_trashed:
        return redirect('files:trash')
    return _browse_redirect(item.parent)


@login_required
@role_required(*_ACCESS_ROLES)
@require_POST
def item_move(request, pk):
    denied = _deny_without_module(request)
    if denied:
        return denied

    item = get_object_or_404(DriveItem, pk=pk, trashed_at__isnull=True)
    parent_id = request.POST.get('parent_id') or None
    try:
        new_parent = _resolve_parent(int(parent_id) if parent_id else None)
        services.move_item(item, new_parent)
        messages.success(request, 'Moved.')
        return _browse_redirect(new_parent)
    except (ValidationError, ValueError, TypeError) as exc:
        messages.error(request, exc.messages[0] if hasattr(exc, 'messages') else str(exc))
        return _browse_redirect(item.parent)


@login_required
@role_required(*_ACCESS_ROLES)
@require_POST
def item_trash(request, pk):
    denied = _deny_without_module(request)
    if denied:
        return denied

    item = get_object_or_404(DriveItem, pk=pk, trashed_at__isnull=True)
    parent = item.parent
    services.trash_item(item)
    messages.success(request, 'Moved to trash.')
    next_url = request.POST.get('next')
    if next_url == 'search':
        return redirect('files:search')
    return _browse_redirect(parent)


@login_required
@role_required(*_ACCESS_ROLES)
@require_POST
def drive_bulk_trash(request):
    denied = _deny_without_module(request)
    if denied:
        return denied

    ids = _parse_item_ids(request)
    parent_id = request.POST.get('parent_id') or None
    parent = services.get_active_folder(parent_id) if parent_id else None

    if not ids:
        messages.error(request, 'Select at least one item to move to trash.')
        return _browse_redirect(parent)

    trashed = services.trash_items(ids)
    if trashed:
        messages.success(
            request,
            f'Moved {trashed} item{"s" if trashed != 1 else ""} to trash.',
        )
    else:
        messages.error(request, 'No matching items to move to trash.')
    return _browse_redirect(parent)


@login_required
@role_required(*_ACCESS_ROLES)
@require_POST
def item_restore(request, pk):
    denied = _deny_without_module(request)
    if denied:
        return denied

    item = get_object_or_404(DriveItem, pk=pk, trashed_at__isnull=False)
    try:
        services.restore_item(item)
        messages.success(request, 'Restored.')
    except ValidationError as exc:
        messages.error(request, exc.messages[0] if hasattr(exc, 'messages') else str(exc))
    return redirect('files:trash')


@login_required
@role_required(*_ACCESS_ROLES)
@require_POST
def item_purge(request, pk):
    denied = _deny_without_module(request)
    if denied:
        return denied

    item = get_object_or_404(DriveItem, pk=pk, trashed_at__isnull=False)
    services.purge_item(item)
    messages.success(request, 'Permanently deleted.')
    return redirect('files:trash')


def _parse_item_ids(request):
    raw = request.POST.getlist('item_ids')
    ids = []
    for value in raw:
        try:
            ids.append(int(value))
        except (TypeError, ValueError):
            continue
    return ids


@login_required
@role_required(*_ACCESS_ROLES)
@require_POST
def trash_bulk_restore(request):
    denied = _deny_without_module(request)
    if denied:
        return denied

    ids = _parse_item_ids(request)
    if not ids:
        messages.error(request, 'Select at least one item to restore.')
        return redirect('files:trash')

    restored, errors = services.restore_items(ids)
    if restored:
        messages.success(
            request,
            f'Restored {restored} item{"s" if restored != 1 else ""}.',
        )
    for err in errors[:5]:
        messages.error(request, err)
    if not restored and not errors:
        messages.error(request, 'No matching items in trash.')
    return redirect('files:trash')


@login_required
@role_required(*_ACCESS_ROLES)
@require_POST
def trash_bulk_purge(request):
    denied = _deny_without_module(request)
    if denied:
        return denied

    ids = _parse_item_ids(request)
    if not ids:
        messages.error(request, 'Select at least one item to delete.')
        return redirect('files:trash')

    purged = services.purge_items(ids)
    if purged:
        messages.success(
            request,
            f'Permanently deleted {purged} item{"s" if purged != 1 else ""}.',
        )
    else:
        messages.error(request, 'No matching items in trash.')
    return redirect('files:trash')


@login_required
@role_required(*_ACCESS_ROLES)
@require_POST
def trash_empty(request):
    denied = _deny_without_module(request)
    if denied:
        return denied

    purged = services.empty_trash()
    if purged:
        messages.success(request, 'Trash emptied.')
    else:
        messages.info(request, 'Trash is already empty.')
    return redirect('files:trash')
