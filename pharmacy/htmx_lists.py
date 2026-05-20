"""HTMX helpers for pharmacy list views."""

from __future__ import annotations

from django.http import QueryDict
from django.shortcuts import render

from core.htmx_utils import is_htmx_request


def list_querystring(get_params: QueryDict, *, exclude_page: bool = True) -> str:
    """Extra query string for pagination links (e.g. ``&q=foo&category=1``)."""
    q = get_params.copy()
    if exclude_page:
        q.pop('page', None)
    encoded = q.urlencode()
    return f'&{encoded}' if encoded else ''


def render_list(request, *, full_template: str, oob_template: str, context: dict):
    """Full page or OOB table swap for filter/pagination HTMX requests."""
    if is_htmx_request(request):
        return render(request, oob_template, context)
    return render(request, full_template, context)
