"""Shared list-view helpers for JSON detection and pagination."""

from __future__ import annotations

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator


def is_json_request(request) -> bool:
    """True when the request content type is JSON (legacy list/API helper)."""
    content_type = (request.content_type or '').lower()
    return content_type.startswith('application/json')


# Back-compat alias used by older view modules
_is_json_request = is_json_request


def paginate_queryset(queryset, request, per_page=10):
    """Paginate a queryset from ``request.GET['page']``."""
    page = request.GET.get('page', 1)
    paginator = Paginator(queryset, per_page)

    try:
        return paginator.page(page)
    except PageNotAnInteger:
        return paginator.page(1)
    except EmptyPage:
        return paginator.page(paginator.num_pages)
