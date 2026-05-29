"""Shared helpers for section sub-navigation inclusion tags."""

from __future__ import annotations

from django.urls import reverse


def view_name(request) -> str:
    match = getattr(request, 'resolver_match', None)
    if not match:
        return ''
    return match.view_name or ''


def nav_item(
    label: str,
    url_name: str,
    *,
    icon: str = '',
    active: bool = False,
    url_args=None,
    url_kwargs=None,
    badge=None,
) -> dict:
    """Build one sub-nav item dict for ``components/sub_nav.html``."""
    if url_args is not None:
        url = reverse(url_name, args=url_args)
    elif url_kwargs is not None:
        url = reverse(url_name, kwargs=url_kwargs)
    else:
        url = reverse(url_name)

    item = {
        'label': label,
        'url': url,
        'icon': icon,
        'active': active,
    }
    if badge is not None:
        item['badge'] = badge
    return item


def is_active(vn: str, *view_names: str) -> bool:
    return vn in view_names


def enrich_subnav(items, *, always_show_nav: bool = False, nav_mb: str | None = None) -> dict:
    """
    Build template context for ``components/sub_nav.html``.

    When the active item is not the first tab, renders breadcrumbs unless
    *always_show_nav* is set (peer-level sections like pharmacy, analytics).
    """
    ctx: dict = {'items': items, 'show_breadcrumbs': False}

    if nav_mb:
        ctx['nav_mb'] = nav_mb

    if len(items) < 2 and not always_show_nav:
        ctx['items'] = []
        return ctx

    if always_show_nav:
        return ctx

    parent = items[0]
    for item in items[1:]:
        if item.get('active'):
            ctx['show_breadcrumbs'] = True
            ctx['bc_crumbs'] = [
                {
                    'label': parent['label'],
                    'url': parent['url'],
                    'icon': parent.get('icon', ''),
                },
                {'label': item['label'], 'icon': item.get('icon', '')},
            ]
            break

    return ctx


def breadcrumb_subnav(crumbs, *, nav_mb: str = 'mb-4') -> dict:
    """Context for breadcrumb-only subnav (no tab strip)."""
    return {
        'show_breadcrumbs': True,
        'bc_crumbs': crumbs,
        'nav_mb': nav_mb,
        'items': [],
    }
