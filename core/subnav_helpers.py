"""Shared helpers for section sub-navigation inclusion tags."""

from __future__ import annotations

from django.urls import reverse


def view_name(request) -> str:
    match = getattr(request, 'resolver_match', None)
    if not match:
        return ''
    return match.view_name or ''


def nav_group(label: str, items: list[dict]) -> dict:
    """Build one labeled group for grouped sub-navigation layouts."""
    return {'label': label, 'items': items}


def nav_dropdown(
    label: str,
    items: list[dict],
    *,
    icon: str = '',
    active: bool | None = None,
) -> dict:
    """Build one dropdown trigger for compact sub-navigation layouts."""
    if active is None:
        active = any(item.get('active') for item in items)
    dropdown = {'label': label, 'items': items, 'active': active, 'icon': icon}
    return dropdown


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


def enrich_subnav(
    items=None,
    *,
    groups=None,
    dropdowns=None,
    always_show_nav: bool = False,
    nav_mb: str | None = None,
    nav_layout: str | None = None,
    nav_aria_label: str | None = None,
) -> dict:
    """
    Build template context for ``components/sub_nav.html``.

    When the active item is not the first tab, renders breadcrumbs unless
    *always_show_nav* is set (peer-level sections like pharmacy, analytics).

    Pass *groups* for multi-row labeled layouts. Pass *dropdowns* for compact
    horizontal menus with Alpine.js flyouts. Use *nav_layout* ``wrapped`` for a
    full-width flex-wrap tab strip on wide flat menus.
    """
    items = list(items or [])
    groups = list(groups or [])
    dropdowns = list(dropdowns or [])
    tab_count = len(items) + len(dropdowns)
    ctx: dict = {
        'items': items,
        'groups': groups,
        'dropdowns': dropdowns,
        'show_breadcrumbs': False,
        'nav_layout': nav_layout or ('grouped' if groups else None),
    }

    if nav_mb:
        ctx['nav_mb'] = nav_mb

    if nav_aria_label:
        ctx['nav_aria_label'] = nav_aria_label

    if groups:
        if not always_show_nav and sum(len(g['items']) for g in groups) < 2:
            ctx['groups'] = []
        return ctx

    if tab_count >= 7 and not ctx['nav_layout']:
        ctx['nav_layout'] = 'wrapped'

    if tab_count < 2 and not always_show_nav:
        ctx['items'] = []
        ctx['dropdowns'] = []
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
