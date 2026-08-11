"""
Shared query helpers for health forms services.

Extracts common patterns from views so view classes stay thin.
"""

from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404

from core.roles import is_patient_role

# Health Profile section keys
PATIENT_HISTORY_SECTIONS = frozenset({'personal', 'medical'})
CLINICAL_SECTIONS = frozenset({'physical', 'diagnostic', 'clinical'})
ALL_HEALTH_PROFILE_SECTIONS = PATIENT_HISTORY_SECTIONS | CLINICAL_SECTIONS

# Minimal fields required before a draft can be submitted for clinic review
SUBMIT_REQUIRED_FIELDS = (
    'last_name',
    'first_name',
    'date_of_birth',
    'gender',
    'designation',
    'department_college_office',
    'mobile_number',
    'email_address',
)

# Guests do not fill institutional affiliation fields
GUEST_SUBMIT_REQUIRED_FIELDS = (
    'last_name',
    'first_name',
    'date_of_birth',
    'gender',
    'designation',
    'mobile_number',
    'email_address',
)

# Prefill keys from patient profile payload that map onto HealthProfileForm fields
HEALTH_PROFILE_PREFILL_FIELDS = (
    'first_name',
    'last_name',
    'middle_name',
    'email_address',
    'gender',
    'civil_status',
    'religion',
    'citizenship',
    'date_of_birth',
    'place_of_birth',
    'age',
    'permanent_address',
    'zip_code',
    'current_address',
    'mobile_number',
    'telephone_number',
    'designation',
    'department_college_office',
    'course',
    'year_level',
    'institution_id',
    'guardian_name',
    'guardian_contact',
    'blood_type',
    'allergies',
    'medical_conditions',
)


def is_clinician(user):
    return getattr(user, 'role', None) in ('staff', 'doctor', 'admin')


def get_forms_for_user(user, model_class):
    """Return role-filtered queryset with common select_related."""
    qs = model_class.objects.all()

    if hasattr(model_class, 'user'):
        qs = qs.select_related('user')
    if hasattr(model_class, 'reviewed_by'):
        qs = qs.select_related('reviewed_by')

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


def can_patient_edit_history(user, form) -> bool:
    """Owner may edit personal/medical only while the form is an incomplete draft."""
    if not is_patient_role(getattr(user, 'role', None)):
        return False
    if getattr(form, 'user_id', None) != getattr(user, 'id', None):
        return False
    return form.status == form.Status.INCOMPLETE


def can_clinician_edit_history(user, form) -> bool:
    """Staff/doctor may assist with personal/medical on incomplete drafts."""
    return is_clinician(user) and form.status == form.Status.INCOMPLETE


def can_clinician_edit_clinical(user, form) -> bool:
    """Staff/doctor edit exam/diagnostics/summary on pending (and assist on incomplete)."""
    if not is_clinician(user):
        return False
    return form.status in (form.Status.PENDING, form.Status.INCOMPLETE)


def editable_sections(user, form) -> frozenset:
    """Section keys the user may POST-save for this health profile form."""
    sections = set()
    if form.status in (form.Status.COMPLETED, form.Status.REJECTED):
        return frozenset()

    if form.status == form.Status.INCOMPLETE:
        if can_patient_edit_history(user, form) or can_clinician_edit_history(user, form):
            sections |= PATIENT_HISTORY_SECTIONS
        if can_clinician_edit_clinical(user, form):
            sections |= CLINICAL_SECTIONS
    elif form.status == form.Status.PENDING:
        if can_clinician_edit_clinical(user, form):
            sections |= CLINICAL_SECTIONS

    return frozenset(sections)


def visible_edit_tabs(user, form, all_tabs):
    """Filter edit tabs: patients on draft see history only; clinicians see all."""
    if is_patient_role(getattr(user, 'role', None)):
        allowed = PATIENT_HISTORY_SECTIONS
        return [tab for tab in all_tabs if tab.get('key') in allowed]
    return list(all_tabs or [])


def can_submit_for_review(user, form) -> bool:
    if form.status != form.Status.INCOMPLETE:
        return False
    if is_patient_role(getattr(user, 'role', None)):
        return getattr(form, 'user_id', None) == getattr(user, 'id', None)
    return is_clinician(user)


def can_cancel_draft(user, form) -> bool:
    """Patient owner or clinician may cancel an incomplete or pending health-profile form."""
    if form.status not in (form.Status.INCOMPLETE, form.Status.PENDING):
        return False
    if is_patient_role(getattr(user, 'role', None)):
        return getattr(form, 'user_id', None) == getattr(user, 'id', None)
    return is_clinician(user)


def can_delete_health_profile(user, form) -> bool:
    """Clinicians may delete unfinished forms; patients may delete their own unfinished forms."""
    if form.status not in (
        form.Status.PENDING,
        form.Status.REJECTED,
        form.Status.INCOMPLETE,
    ):
        return False
    if is_clinician(user):
        return True
    if is_patient_role(getattr(user, 'role', None)):
        return (
            form.status in (form.Status.INCOMPLETE, form.Status.PENDING)
            and getattr(form, 'user_id', None) == getattr(user, 'id', None)
        )
    return False


def cancel_action_label(form) -> str:
    if form.status == form.Status.PENDING:
        return 'Cancel submission'
    if form.status == form.Status.INCOMPLETE:
        return 'Cancel draft'
    return 'Delete form'


def can_review_health_profile(user, form) -> bool:
    return is_clinician(user) and form.status == form.Status.PENDING


def validate_submit_for_review(form) -> list[str]:
    """Return human-readable missing-field messages; empty list means ready."""
    designation = (getattr(form, 'designation', None) or '').strip().lower()
    guest_form = designation == 'guest'
    if not guest_form:
        from core.guest_auth import is_guest_user

        user = getattr(form, 'user', None)
        guest_form = bool(user and is_guest_user(user))

    required = GUEST_SUBMIT_REQUIRED_FIELDS if guest_form else SUBMIT_REQUIRED_FIELDS
    errors = []
    for field_name in required:
        value = getattr(form, field_name, None)
        if value is None or (isinstance(value, str) and not value.strip()):
            label = field_name.replace('_', ' ').title()
            errors.append(f'{label} is required before submitting for review.')
    return errors


def apply_health_profile_prefill(health_form, payload: dict):
    """Copy shared patient-profile payload keys onto a HealthProfileForm instance."""
    for key in HEALTH_PROFILE_PREFILL_FIELDS:
        if key not in payload:
            continue
        value = payload[key]
        if value is None or value == '':
            continue
        if key == 'date_of_birth' and isinstance(value, str):
            from datetime import date
            try:
                value = date.fromisoformat(value)
            except ValueError:
                continue
        setattr(health_form, key, value)
    return health_form


def edit_phase_label(user, form) -> str:
    if form.status == form.Status.INCOMPLETE:
        if is_patient_role(getattr(user, 'role', None)):
            return 'Complete your information'
        return 'Draft — patient information'
    if form.status == form.Status.PENDING:
        if is_clinician(user):
            return 'Complete clinic exam and diagnostics'
        return 'Awaiting clinic exam'
    if form.status == form.Status.COMPLETED:
        return 'Completed'
    if form.status == form.Status.REJECTED:
        return 'Rejected'
    return form.get_status_display()
