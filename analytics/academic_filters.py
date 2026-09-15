"""Shared department / program / year-level filters for analytics views."""

from datetime import timedelta
from urllib.parse import quote

from django.db.models import Q

from core.academic_catalog import patient_catalog_context


def _request_params(request):
    if request is None:
        return None
    if request.method == 'POST' and getattr(request, 'POST', None):
        return request.POST
    return request.GET


def get_academic_filters(request):
    """Parse academic filter GET/POST params (empty string = no filter)."""
    if request is None:
        return {'department': '', 'course': '', 'year_level': ''}
    params = _request_params(request)
    department = (params.get('department') or '').strip()
    course = (params.get('course') or '').strip()
    year_level = (params.get('year_level') or '').strip()
    # Program / year level only apply when a college is selected (profile form flow).
    if not department:
        course = ''
        year_level = ''
    return {
        'department': department,
        'course': course,
        'year_level': year_level,
    }


def academic_filters_active(filters):
    return any(filters.get(k) for k in ('department', 'course', 'year_level'))


def academic_filter_q(filters, prefix='patient__patient_profile__'):
    """Build Q object for profile-based academic filters."""
    q = Q()
    if filters.get('department'):
        q &= Q(**{f'{prefix}department': filters['department']})
    if filters.get('course'):
        q &= Q(**{f'{prefix}course': filters['course']})
    if filters.get('year_level'):
        q &= Q(**{f'{prefix}year_level': filters['year_level']})
    return q


def apply_academic_filters(qs, filters, prefix='patient__patient_profile__'):
    if not academic_filters_active(filters):
        return qs
    return qs.filter(academic_filter_q(filters, prefix=prefix))


def apply_dental_academic_filters(qs, filters):
    """Filter DentalRecord queryset on denormalized academic fields."""
    if not academic_filters_active(filters):
        return qs
    q = Q()
    if filters.get('department'):
        q &= Q(department_college_office=filters['department'])
    if filters.get('course'):
        q &= Q(course=filters['course'])
    if filters.get('year_level'):
        q &= Q(year_level=filters['year_level'])
    return qs.filter(q)


def apply_concern_academic_filters(qs, filters):
    """Filter ConcernRecord queryset on catalog FK names (analytics filter bar)."""
    if not academic_filters_active(filters):
        return qs
    q = Q()
    dept = filters.get('department')
    if dept:
        q &= Q(college_department__name=dept) | Q(department_other=dept)
    if filters.get('course'):
        q &= Q(course_program__name=filters['course'])
    if filters.get('year_level'):
        q &= Q(year_level__name=filters['year_level'])
    return qs.filter(q)


def academic_filter_query_string(filters, *, extra=None):
    """Serialize filters for URL query strings."""
    parts = list(extra or [])
    for key in ('department', 'course', 'year_level'):
        val = (filters or {}).get(key, '')
        if val:
            parts.append(f'{key}={quote(val)}')
    return f'&{"&".join(parts)}' if parts else ''


def period_presets(date_from, date_to, request=None):
    """Quick date-range shortcuts; preserve academic filters in preset URLs."""
    from django.utils import timezone

    today = timezone.localdate()
    filters = get_academic_filters(request) if request else {}
    suffix = academic_filter_query_string(filters)
    presets = []
    for label, days in (('30 days', 30), ('90 days', 90), ('6 months', 180)):
        preset_from = today - __import__('datetime').timedelta(days=days)
        presets.append({
            'label': label,
            'date_from': preset_from,
            'date_to': today,
            'active': date_from == preset_from and date_to == today,
            'query_suffix': suffix,
        })
    return presets


def active_filter_labels(filters):
    labels = []
    if filters.get('department'):
        labels.append(f"Dept: {filters['department']}")
    if filters.get('course'):
        labels.append(f"Program: {filters['course']}")
    if filters.get('year_level'):
        labels.append(f"Year: {filters['year_level']}")
    return labels


def analytics_filter_context(request, date_from, date_to):
    """Template context for the shared analytics filter bar."""
    from .forms import AcademicAnalyticsFilterForm

    filters = get_academic_filters(request)
    catalog = patient_catalog_context()
    params = _request_params(request) if request else None
    illness_q = (params.get('illness_category') or '').strip() if params else ''
    concern_q = (params.get('q') or '').strip() if params else ''
    selected_type = (params.get('type') or '').strip() if params else ''

    return {
        'academic_filters': filters,
        'academic_filter_form': AcademicAnalyticsFilterForm(
            initial={
                'department': filters['department'],
                'course': filters['course'],
                'year_level': filters['year_level'],
                'date_from': date_from,
                'date_to': date_to,
            }
        ),
        'academic_query': academic_filter_query_string(filters),
        'active_filter_labels': active_filter_labels(filters),
        'has_academic_filters': academic_filters_active(filters),
        'college_options_json': catalog['college_options_json'],
        'course_options_by_college_json': catalog['course_options_by_college_json'],
        'year_level_options_by_college_json': catalog['year_level_options_by_college_json'],
        'college_options': catalog['college_options'],
        'filter_bar_config_json': __import__('json').dumps({
            'department': filters['department'],
            'course': filters['course'] if filters['department'] else '',
            'year_level': filters['year_level'] if filters['department'] else '',
            'illness_category': illness_q,
            'concern_search': concern_q,
            'date_from': date_from.isoformat() if date_from else '',
            'date_to': date_to.isoformat() if date_to else '',
            'selected_type': selected_type,
        }),
        'selected_type': selected_type,
        'illness_filter': illness_q,
        'concern_filter': concern_q,
        'pagination_query': build_pagination_query(date_from, date_to, request),
        'clear_filters_href': clear_filters_href(request),
        'has_clearable_filters': _has_clearable_filters(
            request, date_from, date_to, filters, illness_q, concern_q,
        ),
    }


def build_pagination_query(date_from, date_to, request=None):
    """Query fragment (leading &) for pagination links: dates + academic + type + illness."""
    parts = []
    if date_from:
        parts.append(f'date_from={date_from.isoformat()}')
    if date_to:
        parts.append(f'date_to={date_to.isoformat()}')
    params = _request_params(request) if request else None
    selected_type = (params.get('type') or '').strip() if params else ''
    illness_q = (params.get('illness_category') or '').strip() if params else ''
    if selected_type:
        parts.append(f'type={quote(selected_type)}')
    if illness_q:
        parts.append(f'illness_category={quote(illness_q)}')
    academic = academic_filter_query_string(get_academic_filters(request) if request else {}).lstrip('&')
    if academic:
        parts.append(academic)
    return f'&{"&".join(parts)}' if parts else ''


def page_window_numbers(page_obj, adjacent=1):
    """Compact page list with None sentinels for ellipsis gaps."""
    if page_obj is None or not getattr(page_obj, 'paginator', None):
        return []
    num_pages = page_obj.paginator.num_pages
    current = page_obj.number
    pages = set([1, num_pages, current])
    for offset in range(1, adjacent + 1):
        if current - offset >= 1:
            pages.add(current - offset)
        if current + offset <= num_pages:
            pages.add(current + offset)
    result = []
    previous = 0
    for page in sorted(pages):
        if page > previous + 1:
            result.append('')
        result.append(page)
        previous = page
    return result


def clear_filters_href(request=None):
    """Reset to default 90-day window; keep insight/report type if present."""
    from django.utils import timezone

    today = timezone.localdate()
    default_from = today - timedelta(days=90)
    parts = [f'date_from={default_from.isoformat()}', f'date_to={today.isoformat()}']
    params = _request_params(request) if request else None
    selected_type = (params.get('type') or '').strip() if params else ''
    if selected_type:
        parts.append(f'type={quote(selected_type)}')
    return f'?{"&".join(parts)}'


def _has_clearable_filters(request, date_from, date_to, filters, illness_q, concern_q=''):
    from django.utils import timezone

    today = timezone.localdate()
    default_from = today - timedelta(days=90)
    if academic_filters_active(filters) or illness_q or concern_q:
        return True
    return date_from != default_from or date_to != today


def write_academic_filter_csv_rows(writer, filters):
    if not academic_filters_active(filters):
        return
    writer.writerow(['Academic filters'])
    if filters.get('department'):
        writer.writerow(['Department', filters['department']])
    if filters.get('course'):
        writer.writerow(['Program', filters['course']])
    if filters.get('year_level'):
        writer.writerow(['Year level', filters['year_level']])
    writer.writerow([])


def filtered_clinical_counts(date_from, date_to, filters):
    """Appointment and medical record counts for a filtered patient segment."""
    from appointments.models import Appointment
    from medical_records.models import MedicalRecord

    appt_qs = Appointment.objects.filter(date__gte=date_from, date__lte=date_to)
    mr_qs = MedicalRecord.objects.filter(
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
    )
    appt_qs = apply_academic_filters(appt_qs, filters)
    mr_qs = apply_academic_filters(mr_qs, filters)
    return {
        'filtered_appointments': appt_qs.count(),
        'filtered_medical_records': mr_qs.count(),
    }
