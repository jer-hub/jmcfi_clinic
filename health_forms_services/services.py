"""
Shared query helpers for health forms services.

Extracts common patterns from views so view classes stay thin.
"""

from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404


def get_forms_for_user(user, model_class):
    """Return role-filtered queryset with common select_related."""
    qs = model_class.objects.all()

    if hasattr(model_class, 'user'):
        qs = qs.select_related('user')
    if hasattr(model_class, 'reviewed_by'):
        qs = qs.select_related('reviewed_by')

    from core.roles import is_patient_role
    if is_patient_role(user.role):
        qs = qs.filter(user=user)

    return qs


def get_form_or_403(user, model_class, pk, extra_select_related=None):
    """Return single form object with role-based access check (404 if denied)."""
    qs = model_class.objects.all()

    selects = []
    if hasattr(model_class, 'user'):
        selects.append('user')
    if hasattr(model_class, 'reviewed_by'):
        selects.append('reviewed_by')
    if extra_select_related:
        selects.extend(extra_select_related)

    if selects:
        qs = qs.select_related(*selects)

    from core.roles import is_patient_role
    if is_patient_role(user.role):
        return get_object_or_404(qs, pk=pk, user=user)
    return get_object_or_404(qs, pk=pk)


def apply_search_and_filter(queryset, search, status_filter, search_fields):
    """Apply search and status filter; return (filtered_qs, search_value, status_value)."""
    if search and search_fields:
        query = Q()
        for field in search_fields:
            query |= Q(**{f'{field}__icontains': search})
        queryset = queryset.filter(query)

    if status_filter:
        queryset = queryset.filter(status=status_filter)

    return queryset


def paginate_forms(queryset, request, per_page=15):
    """Paginate with consistent page size."""
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get('page', 1)
    return paginator.get_page(page_number)
