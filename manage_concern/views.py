from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.academic_catalog import active_colleges_queryset, course_optional_by_college
from core.decorators import role_required
from core.doctor_access import MODULE_MANAGE_CONCERN, has_clinical_module
from core.htmx_utils import is_htmx_request
from core.models import CourseProgram, YearLevelOption
from core.roles import PATIENT_ROLE_VALUES, role_matches
from core.utils import patient_search_q, student_display_name

from .forms import ConcernRecordForm
from .models import ConcernRecord

LIST_PAGE_SIZE = 10
_ACCESS_ROLES = ('staff', 'doctor')


def _deny_without_module(request):
    from core.access_control import AccessReason, access_denied_response

    if has_clinical_module(request.user, MODULE_MANAGE_CONCERN):
        return None
    return access_denied_response(
        request,
        status_code=403,
        reason=AccessReason.FORBIDDEN,
    )


def _concern_list_querystring_from_filters(filters: dict) -> str:
    """Extra query string for pagination links from cleaned filter values."""
    q = QueryDict(mutable=True)
    mapping = {
        'search': filters.get('search_query') or '',
        'date_from': filters.get('date_from') or '',
        'date_to': filters.get('date_to') or '',
        'affiliation': filters.get('affiliation') or '',
        'department': filters.get('department_id') or '',
        'program': filters.get('program_id') or '',
        'year_level': filters.get('year_level_id') or '',
    }
    for key, value in mapping.items():
        text = str(value).strip()
        if text:
            q[key] = text
    encoded = q.urlencode()
    return f'&{encoded}' if encoded else ''


def _parse_optional_pk(raw):
    value = (raw or '').strip()
    if not value:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _apply_concern_list_filters(qs, get_params: QueryDict):
    search = (get_params.get('search') or '').strip()
    date_from = (get_params.get('date_from') or '').strip()
    date_to = (get_params.get('date_to') or '').strip()
    affiliation = (get_params.get('affiliation') or '').strip()
    department_id = _parse_optional_pk(get_params.get('department'))
    program_id = _parse_optional_pk(get_params.get('program'))
    year_level_id = _parse_optional_pk(get_params.get('year_level'))

    valid_affiliations = {choice.value for choice in ConcernRecord.AffiliationType}
    if affiliation not in valid_affiliations:
        affiliation = ''

    # Academic catalog filters depend on affiliation.
    show_department = affiliation != ConcernRecord.AffiliationType.OTHERS
    show_program_year = affiliation in ('', ConcernRecord.AffiliationType.CATALOG)

    if not show_department:
        department_id = None
    if not show_program_year:
        program_id = None
        year_level_id = None
    elif not department_id:
        # Program/year only make sense after a department is chosen.
        program_id = None
        year_level_id = None

    if search:
        qs = qs.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(middle_name__icontains=search)
            | Q(concerns__icontains=search)
            | Q(management_treatment__icontains=search)
            | Q(disposition__icontains=search)
            | Q(department_other__icontains=search)
            | Q(college_department__name__icontains=search)
            | Q(course_program__name__icontains=search)
            | Q(year_level__name__icontains=search)
            | Q(patient_user__email__icontains=search)
            | Q(patient_user__first_name__icontains=search)
            | Q(patient_user__last_name__icontains=search)
        )

    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)

    if affiliation:
        qs = qs.filter(affiliation_type=affiliation)

    if department_id:
        qs = qs.filter(college_department_id=department_id)
        if program_id and not CourseProgram.objects.filter(
            pk=program_id, college_department_id=department_id
        ).exists():
            program_id = None
        if year_level_id and not YearLevelOption.objects.filter(
            pk=year_level_id, college_department_id=department_id
        ).exists():
            year_level_id = None

    if program_id:
        qs = qs.filter(course_program_id=program_id)
    if year_level_id:
        qs = qs.filter(year_level_id=year_level_id)

    return qs, {
        'search_query': search,
        'date_from': date_from,
        'date_to': date_to,
        'affiliation': affiliation,
        'department_id': department_id,
        'program_id': program_id,
        'year_level_id': year_level_id,
        'show_department_filter': show_department,
        'show_program_year_filters': show_program_year,
    }


def _concern_filter_catalog(*, department_id=None, show_program_year=True):
    colleges = list(active_colleges_queryset())
    if not show_program_year or not department_id:
        return {
            'filter_departments': colleges,
            'filter_programs': [],
            'filter_year_levels': [],
        }

    programs = CourseProgram.objects.select_related('college_department').filter(
        is_active=True,
        college_department__is_active=True,
        college_department_id=department_id,
    )
    years = YearLevelOption.objects.select_related('college_department').filter(
        is_active=True,
        college_department__is_active=True,
        college_department_id=department_id,
    )
    return {
        'filter_departments': colleges,
        'filter_programs': list(programs.order_by('name')),
        'filter_year_levels': list(years.order_by('sort_order', 'name')),
    }


def _build_concern_list_context(request):
    get_params = request.GET
    qs = ConcernRecord.objects.select_related(
        'college_department',
        'course_program',
        'year_level',
        'patient_user',
        'created_by',
    )
    qs, filters = _apply_concern_list_filters(qs, get_params)
    page_obj = Paginator(qs, LIST_PAGE_SIZE).get_page(get_params.get('page'))
    has_filters = any(
        bool(value)
        for key, value in filters.items()
        if key not in ('show_department_filter', 'show_program_year_filters')
    )
    catalog = _concern_filter_catalog(
        department_id=filters.get('department_id'),
        show_program_year=filters.get('show_program_year_filters', True),
    )
    return {
        'page_obj': page_obj,
        'records': page_obj.object_list,
        'total_count': page_obj.paginator.count,
        'has_filters': has_filters,
        'mc_list_querystring': _concern_list_querystring_from_filters(filters),
        **filters,
        **catalog,
    }


def _catalog_colleges():
    """[{id, name}, ...] for profile-style searchable college combobox.

    Synthetic options Employee / Others are prepended in the form JS.
    """
    return [
        {'id': college.pk, 'name': college.name, 'kind': 'catalog'}
        for college in active_colleges_queryset()
    ]


def _catalog_programs_by_college():
    """College name -> [{id, name}, ...] for dependent program selects."""
    mapping = {}
    qs = CourseProgram.objects.select_related('college_department').filter(
        is_active=True,
        college_department__is_active=True,
    ).order_by('college_department__name', 'name')
    for course in qs:
        mapping.setdefault(course.college_department.name, []).append(
            {'id': course.pk, 'name': course.name}
        )
    return mapping


def _catalog_year_levels_by_college():
    """College name -> [{id, name}, ...] for dependent year-level selects."""
    mapping = {}
    qs = YearLevelOption.objects.select_related('college_department').filter(
        is_active=True,
        college_department__is_active=True,
    ).order_by('college_department__name', 'sort_order', 'name')
    for item in qs:
        mapping.setdefault(item.college_department.name, []).append(
            {'id': item.pk, 'name': item.name}
        )
    return mapping


def _profile_academic_payload(user):
    profile = getattr(user, 'patient_profile', None) or getattr(user, 'staff_profile', None)
    return {
        'department': getattr(profile, 'department', '') if profile else '',
        'course': getattr(profile, 'course', '') if profile else '',
        'year_level': getattr(profile, 'year_level', '') if profile else '',
        'middle_name': getattr(profile, 'middle_name', '') if profile else '',
        'is_employee': bool(getattr(profile, 'is_employee', False)) if profile else False,
    }


def _record_form_context(form, *, title, subtitle, submit_label):
    user = form.instance.patient_user if getattr(form.instance, "patient_user_id", None) else None
    selected_user = None
    if user:
        selected_user = {
            'id': user.id,
            'name': student_display_name(user),
            'email': user.email,
        }
    colleges = _catalog_colleges()
    current_college = getattr(form.instance, 'college_department', None)
    if current_college and current_college.pk and not any(
        c['id'] == current_college.pk for c in colleges
    ):
        colleges = [
            {'id': current_college.pk, 'name': current_college.name, 'kind': 'catalog'},
            *colleges,
        ]
        colleges.sort(key=lambda c: c['name'])

    instance = form.instance
    initial_affiliation = (
        form['affiliation_type'].value()
        if form.is_bound
        else getattr(instance, 'affiliation_type', ConcernRecord.AffiliationType.CATALOG)
        or ConcernRecord.AffiliationType.CATALOG
    )
    initial_department_other = (
        form['department_other'].value()
        if form.is_bound
        else getattr(instance, 'department_other', '') or ''
    )
    return {
        'form': form,
        'title': title,
        'subtitle': subtitle,
        'submit_label': submit_label,
        'patient_search_url': reverse('manage_concern:search_users'),
        'patient_prefill_template': reverse('manage_concern:user_prefill', args=[0]),
        'catalog_colleges': colleges,
        'catalog_courses': _catalog_programs_by_college(),
        'catalog_year_levels': _catalog_year_levels_by_college(),
        'catalog_course_optional': course_optional_by_college(),
        'selected_user': selected_user,
        'initial_affiliation_type': initial_affiliation,
        'initial_department_other': initial_department_other,
    }


@login_required
@role_required(*_ACCESS_ROLES)
def concern_list(request):
    denied = _deny_without_module(request)
    if denied:
        return denied

    context = _build_concern_list_context(request)
    if is_htmx_request(request):
        return render(request, 'manage_concern/_concern_list_filter_oob.html', context)
    return render(request, 'manage_concern/concern_list.html', context)


@login_required
@role_required(*_ACCESS_ROLES)
def concern_create(request):
    denied = _deny_without_module(request)
    if denied:
        return denied

    if request.method == 'POST':
        form = ConcernRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.created_by = request.user
            record.save()
            messages.success(request, 'Concern record created.')
            return redirect('manage_concern:concern_detail', pk=record.pk)
    else:
        form = ConcernRecordForm()

    return render(
        request,
        'manage_concern/concern_form.html',
        _record_form_context(
            form,
            title='New Concern',
            subtitle='Log a clinic concern and management rendered',
            submit_label='Create record',
        ),
    )


@login_required
@role_required(*_ACCESS_ROLES)
def concern_detail(request, pk):
    denied = _deny_without_module(request)
    if denied:
        return denied

    record = get_object_or_404(
        ConcernRecord.objects.select_related(
            'college_department',
            'course_program',
            'year_level',
            'patient_user',
            'created_by',
        ),
        pk=pk,
    )
    return render(
        request,
        'manage_concern/concern_detail.html',
        {'record': record},
    )


@login_required
@role_required(*_ACCESS_ROLES)
def concern_edit(request, pk):
    denied = _deny_without_module(request)
    if denied:
        return denied

    record = get_object_or_404(
        ConcernRecord.objects.select_related(
            'college_department',
            'course_program',
            'year_level',
            'patient_user',
        ),
        pk=pk,
    )
    if request.method == 'POST':
        form = ConcernRecordForm(request.POST, instance=record)
        if form.is_valid():
            form.save()
            messages.success(request, 'Concern record updated.')
            return redirect('manage_concern:concern_detail', pk=record.pk)
    else:
        form = ConcernRecordForm(instance=record)

    return render(
        request,
        'manage_concern/concern_form.html',
        _record_form_context(
            form,
            title='Edit Concern',
            subtitle=record.display_name,
            submit_label='Save changes',
        ),
    )


@login_required
@role_required(*_ACCESS_ROLES)
@require_POST
def concern_delete(request, pk):
    denied = _deny_without_module(request)
    if denied:
        return denied

    record = get_object_or_404(ConcernRecord, pk=pk)
    label = record.display_name
    record.delete()
    messages.success(request, f'Concern record for {label} deleted.')
    return redirect('manage_concern:concern_list')


@login_required
@role_required(*_ACCESS_ROLES)
def search_users(request):
    denied = _deny_without_module(request)
    if denied:
        return denied

    query = (request.GET.get('q') or '').strip()
    if len(query) < 2:
        return JsonResponse([], safe=False)

    from core.guest_auth import exclude_guest_users

    user_model = get_user_model()
    users = (
        exclude_guest_users(
            user_model.objects.filter(
                Q(is_active=True)
                & ~Q(role='admin')
                & (
                    patient_search_q(query)
                    | Q(first_name__icontains=query)
                    | Q(last_name__icontains=query)
                    | Q(email__icontains=query)
                )
            )
        )
        .select_related('patient_profile', 'staff_profile')
        .distinct()[:10]
    )

    data = []
    for user in users:
        academic = _profile_academic_payload(user)
        data.append(
            {
                'id': user.id,
                'name': student_display_name(user) if role_matches(user.role, *PATIENT_ROLE_VALUES) else user.get_full_name().strip() or user.email,
                'email': user.email,
                **academic,
            }
        )
    return JsonResponse(data, safe=False)


@login_required
@role_required(*_ACCESS_ROLES)
def user_prefill(request, user_id):
    denied = _deny_without_module(request)
    if denied:
        return denied

    user = get_object_or_404(get_user_model(), pk=user_id, is_active=True)
    academic = _profile_academic_payload(user)
    return JsonResponse(
        {
            'id': user.id,
            'first_name': user.first_name or '',
            'last_name': user.last_name or '',
            **academic,
        }
    )
