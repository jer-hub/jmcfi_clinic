import json
import re

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse, QueryDict
from django.utils import timezone
from urllib.parse import urlparse

from core.htmx_utils import is_htmx_request
from core.roles import PATIENT_ROLE_VALUES, is_patient_role
from core.utils import student_display_name
from django.utils.dateparse import parse_date
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from django.db.models import Q

from .models import MedicalRecord
from core.notification_delivery import notify_user
from appointments.models import Appointment
from core.clinical_audit import log_clinical_access, _medical_record_label
from core.decorators import role_required
from dental_records.models import DentalRecord
from health_forms_services.models import Prescription
from health_forms_services.forms import PrescriptionPatientForm
from django.contrib.auth import get_user_model
from django.test import RequestFactory


User = get_user_model()


def _is_missed_pending_appointment(appointment) -> bool:
    """True if appointment is missed or still pending after its scheduled slot."""
    if not appointment:
        return False
    if appointment.status == 'missed':
        return True
    if appointment.status != 'pending':
        return False
    now = timezone.localtime()
    if appointment.date < now.date():
        return True
    if appointment.date == now.date() and appointment.time < now.time():
        return True
    return False


def _pending_missed_q():
    """Q() on Appointment: missed status or pending with slot start in the past."""
    now = timezone.localtime()
    past_slot = Q(date__lt=now.date()) | Q(date=now.date(), time__lt=now.time())
    return Q(status='missed') | (Q(status='pending') & past_slot)


def _record_linked_pending_missed_q():
    """Q() on MedicalRecord: linked appointment missed or pending past slot."""
    now = timezone.localtime()
    past_slot = Q(appointment__date__lt=now.date()) | Q(
        appointment__date=now.date(), appointment__time__lt=now.time()
    )
    return Q(appointment__status='missed') | (Q(appointment__status='pending') & past_slot)


def _apply_physician_user_to_initial(initial, physician_user):
    """Set prescription physician fields from a doctor user."""
    if not physician_user or getattr(physician_user, 'role', None) != 'doctor':
        return
    initial['physician'] = physician_user.id
    initial['physician_name'] = physician_user.get_full_name()
    staff_profile = getattr(physician_user, 'staff_profile', None)
    if staff_profile:
        initial['license_no'] = staff_profile.license_number or ''
        initial['ptr_no'] = staff_profile.ptr_no or ''


def _build_prescription_initial(
    student,
    doctor=None,
    acting_user=None,
    appointment=None,
):
    """Build PrescriptionPatientForm initial data.

    Prescription date defaults to the appointment date when present, else today.
    Physician comes from the authenticated doctor or the assigned appointment doctor.
    """
    today = timezone.localdate()
    prescription_date = appointment.date if appointment and appointment.date else today
    initial = {'date': prescription_date}

    if not student:
        prescribing = None
        if acting_user and acting_user.role == 'doctor':
            prescribing = acting_user
        elif doctor and getattr(doctor, 'role', None) == 'doctor':
            prescribing = doctor
        if prescribing:
            _apply_physician_user_to_initial(initial, prescribing)
        return initial

    initial.setdefault('patient_name', student_display_name(student))

    profile = getattr(student, 'patient_profile', None)
    if profile and getattr(profile, 'date_of_birth', None):
        initial['age'] = today.year - profile.date_of_birth.year - (
            (today.month, today.day) < (profile.date_of_birth.month, profile.date_of_birth.day)
        )

    if profile and getattr(profile, 'gender', None):
        initial['gender'] = profile.gender

    prescribing = None
    if acting_user and acting_user.role == 'doctor':
        prescribing = acting_user
    elif doctor and getattr(doctor, 'role', None) == 'doctor':
        prescribing = doctor
    if prescribing:
        _apply_physician_user_to_initial(initial, prescribing)

    return initial


def _collect_medication_entries(post_data):
    med_item_pattern = re.compile(r'^med_item_(\d+)_name$')
    med_indices = set()

    for key in post_data:
        match = med_item_pattern.match(key)
        if match:
            med_indices.add(int(match.group(1)))

    entries = []
    for idx in sorted(med_indices):
        entries.append({
            'name': post_data.get(f'med_item_{idx}_name', '').strip(),
            'dosage': post_data.get(f'med_item_{idx}_dosage', '').strip(),
            'frequency': post_data.get(f'med_item_{idx}_frequency', '').strip(),
            'duration': post_data.get(f'med_item_{idx}_duration', '').strip(),
            'quantity': post_data.get(f'med_item_{idx}_quantity', '').strip(),
            'instructions': post_data.get(f'med_item_{idx}_instructions', '').strip(),
        })

    return entries or [{'name': '', 'dosage': '', 'frequency': '', 'duration': '', 'quantity': '', 'instructions': ''}]


def _form_state_from_request(request):
    if request.method != 'POST':
        return {}
    return {
        'blood_pressure': request.POST.get('blood_pressure', ''),
        'temperature': request.POST.get('temperature', ''),
        'heart_rate': request.POST.get('heart_rate', ''),
        'weight': request.POST.get('weight', ''),
        'treatment': request.POST.get('treatment', ''),
        'lab_results': request.POST.get('lab_results', ''),
    }


def _parse_vital_signs_from_post(post):
    """Return (vital_signs dict, None) on success, or (None, (field_key, message)) on failure.

    field_key is 'heart_rate' or 'weight' for inline display.
    """
    vital_signs = {}

    blood_pressure = post.get('blood_pressure', '').strip()
    if blood_pressure:
        vital_signs['blood_pressure'] = blood_pressure

    temperature = post.get('temperature', '').strip()
    if temperature:
        vital_signs['temperature'] = temperature

    heart_rate = post.get('heart_rate', '').strip()
    if heart_rate:
        try:
            hr_value = int(heart_rate)
            if 40 <= hr_value <= 200:
                vital_signs['heart_rate'] = heart_rate
            else:
                return None, ('heart_rate', 'Heart rate must be between 40 and 200 bpm.')
        except ValueError:
            return None, ('heart_rate', 'Heart rate must be a valid number.')

    weight = post.get('weight', '').strip()
    if weight:
        try:
            weight_value = float(weight)
            if 20.0 <= weight_value <= 300.0:
                vital_signs['weight'] = weight
            else:
                return None, ('weight', 'Weight must be between 20 and 300 kg.')
        except ValueError:
            return None, ('weight', 'Weight must be a valid number.')

    return vital_signs, None


def _student_age_years(student):
    profile = getattr(student, 'patient_profile', None) if student else None
    if not profile or not getattr(profile, 'date_of_birth', None):
        return None
    today = timezone.localdate()
    dob = profile.date_of_birth
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _prescription_form_for_request(
    request,
    *,
    student=None,
    doctor=None,
    acting_user=None,
    appointment=None,
):
    """Build PrescriptionPatientForm; enrich POST so a new prescription can always be saved."""
    initial = _build_prescription_initial(
        student,
        doctor=doctor,
        acting_user=acting_user,
        appointment=appointment,
    )
    if request.method != 'POST':
        return PrescriptionPatientForm(initial=initial)

    data = request.POST.copy()
    if not data.get('date', '').strip():
        fallback = initial.get('date') or timezone.localdate()
        data['date'] = fallback.isoformat() if hasattr(fallback, 'isoformat') else str(fallback)
    if student:
        if not data.get('patient_name', '').strip():
            data['patient_name'] = student_display_name(student)
        profile = getattr(student, 'patient_profile', None)
        if profile:
            if not data.get('gender'):
                data['gender'] = profile.gender or ''
            if not data.get('address', '').strip() and profile.address:
                data['address'] = profile.address
            if not data.get('age'):
                age = _student_age_years(student)
                if age is not None:
                    data['age'] = str(age)
    return PrescriptionPatientForm(data, initial=initial)


def _build_create_medical_record_context(
    request,
    *,
    appointment=None,
    student=None,
    prescription_form=None,
    is_direct_patient_flow=False,
    vitals_errors=None,
    lab_errors=None,
):
    if appointment and not student:
        student = appointment.patient

    if prescription_form is None:
        prescription_form = _prescription_form_for_request(
            request,
            student=student,
            doctor=appointment.doctor if appointment else None,
            acting_user=request.user,
            appointment=appointment,
        )

    medication_entries = (
        _collect_medication_entries(request.POST)
        if request.method == 'POST'
        else _collect_medication_entries({})
    )

    context = {
        'appointment': appointment,
        'patient': student,
        'patient_age': _student_age_years(student),
        'is_direct_patient_flow': is_direct_patient_flow,
        'prescription_form': prescription_form,
        'form_state': _form_state_from_request(request),
        'medication_entries_json': json.dumps(medication_entries),
        'vitals_errors': vitals_errors or {},
        'lab_errors': lab_errors or {},
    }

    return context


def _render_create_for_patient(request, student, *, prescription_form=None, vitals_errors=None):
    return render(
        request,
        'medical_records/create_medical_record_for_patient.html',
        _direct_patient_create_context(
            request, student, prescription_form=prescription_form, vitals_errors=vitals_errors
        ),
    )




def _direct_patient_create_context(request, student, *, prescription_form=None, vitals_errors=None):
    """Context for walk-in create (no appointment): always a fresh prescription."""
    if prescription_form is None:
        prescription_form = _prescription_form_for_request(
            request,
            student=student,
            acting_user=request.user,
        )
    return _build_create_medical_record_context(
        request,
        student=student,
        prescription_form=prescription_form,
        is_direct_patient_flow=True,
        vitals_errors=vitals_errors,
    )


def _appointment_create_context(request, appointment, *, prescription_form=None, vitals_errors=None):
    """Context for create-from-appointment."""
    if prescription_form is None:
        prescription_form = _prescription_form_for_request(
            request,
            student=appointment.patient,
            doctor=appointment.doctor,
            acting_user=request.user,
            appointment=appointment,
        )
    return _build_create_medical_record_context(
        request,
        appointment=appointment,
        prescription_form=prescription_form,
        vitals_errors=vitals_errors,
    )


def _render_create_from_appointment(request, appointment, *, prescription_form=None, vitals_errors=None):
    return render(
        request,
        'medical_records/create_medical_record_from_appointment.html',
        _appointment_create_context(
            request, appointment, prescription_form=prescription_form, vitals_errors=vitals_errors
        ),
    )


def _save_prescription_for_medical_record(request, prescription_form, medical_record):
    """Create a new prescription linked to a new medical record.

    Raises ValueError if the prescription cannot be created (rolls back the
    surrounding atomic block).
    """
    from health_forms_services.models import PrescriptionItem

    diagnosis_val = (
        (prescription_form.data.get('diagnosis') or '').strip()
        or medical_record.diagnosis
        or ''
    )
    if not diagnosis_val:
        raise ValueError('Diagnosis is required to create a prescription.')

    if not prescription_form.is_valid():
        raise ValueError(f'Invalid prescription data: {prescription_form.errors.as_json()}')

    diagnosis_val = prescription_form.cleaned_data.get('diagnosis', '') or diagnosis_val
    instructions_val = prescription_form.cleaned_data.get('instructions', '')
    medications_val = request.POST.get('medications', '').strip()
    body_parts = []
    if diagnosis_val:
        body_parts.append(f"Diagnosis:\n{diagnosis_val}")
    if medications_val:
        body_parts.append(f"Medications:\n{medications_val}")
    if instructions_val:
        body_parts.append(f"Instructions:\n{instructions_val}")
    prescription_body = '\n\n'.join(body_parts)

    prescription_obj = prescription_form.save(commit=False)
    prescription_obj.user = request.user
    prescription_obj.medical_record = medical_record
    prescription_obj.status = Prescription.Status.COMPLETED
    prescription_obj.prescription_body = prescription_body
    if not prescription_obj.date:
        prescription_obj.date = timezone.localdate()
    prescription_obj.save()

    med_item_pattern = re.compile(r'^med_item_(\d+)_name$')
    med_indices = set()
    for key in request.POST:
        match = med_item_pattern.match(key)
        if match:
            med_indices.add(int(match.group(1)))

    for idx in sorted(med_indices):
        name = request.POST.get(f'med_item_{idx}_name', '').strip()
        if name:
            PrescriptionItem.objects.create(
                prescription=prescription_obj,
                medication_name=name,
                dosage=request.POST.get(f'med_item_{idx}_dosage', '').strip(),
                frequency=request.POST.get(f'med_item_{idx}_frequency', '').strip(),
                duration=request.POST.get(f'med_item_{idx}_duration', '').strip(),
                quantity=request.POST.get(f'med_item_{idx}_quantity', '').strip(),
                instructions=request.POST.get(f'med_item_{idx}_instructions', '').strip(),
            )

    return prescription_obj


def paginate_queryset(queryset, request, per_page=10):
    """Helper function for pagination"""
    page = request.GET.get('page', 1)
    paginator = Paginator(queryset, per_page)
    
    try:
        paginated_items = paginator.page(page)
    except PageNotAnInteger:
        paginated_items = paginator.page(1)
    except EmptyPage:
        paginated_items = paginator.page(paginator.num_pages)
    
    return paginated_items


def _effective_medical_list_get_params(request):
    """Filters for list stat OOB: prefer HX-Current-URL query when HTMX POST comes from the list."""
    raw = (request.headers.get('HX-Current-URL') or '').strip()
    if raw:
        q = urlparse(raw).query
        if q:
            return QueryDict(q)
    return request.GET


def _medical_list_request_for_params(original_request, get_params: QueryDict):
    """Build a GET request carrying list filters (for pagination + table partial HTML)."""
    rf = RequestFactory()
    path = reverse('medical_records:medical_records')
    list_req = rf.get(
        path,
        data=get_params.dict(),
        HTTP_HOST=original_request.get_host(),
        secure=original_request.is_secure(),
    )
    list_req.user = original_request.user
    return list_req


_MEDICAL_LIST_STATUS_KEYS = ('pending', 'missed', 'confirmed', 'completed', 'cancelled')


def _effective_timeline_row_status(row) -> str:
    """Display/filter status for a medical list timeline row."""
    if row.get('missed_slot'):
        return 'missed'
    if row['row_type'] == 'record':
        record = row['record']
        return record.timeline_filter_status(missed_slot=bool(row.get('missed_slot')))
    return row['appointment'].status


def _medical_list_stat_filter_url(get_params: QueryDict, status_key: str) -> str:
    """Toggle *status_key* in list query string; preserve other filters."""
    q = get_params.copy()
    current = (q.get('status') or '').strip()
    if current == status_key:
        q.pop('status', None)
    else:
        q['status'] = status_key
    q.pop('page', None)
    base = reverse('medical_records:medical_records')
    encoded = q.urlencode()
    return f'{base}?{encoded}' if encoded else base


def _medical_list_stat_filter_urls(get_params: QueryDict) -> dict[str, str]:
    return {key: _medical_list_stat_filter_url(get_params, key) for key in _MEDICAL_LIST_STATUS_KEYS}


def _medical_list_querystring(get_params: QueryDict) -> str:
    """Preserve active filters in HTMX pagination links (exclude page)."""
    q = get_params.copy()
    q.pop('page', None)
    encoded = q.urlencode()
    return f'&{encoded}' if encoded else ''


def _build_unpaginated_medical_timeline(request_user, get_params):
    """
    Build timeline row dicts and status_totals (same rules as medical_records list), unpaginated.
    get_params: QueryDict-like (.get).
    """
    if is_patient_role(request_user.role):
        records = MedicalRecord.objects.filter(patient=request_user)
        appointments = Appointment.objects.filter(patient=request_user)
    elif request_user.role in ['staff', 'doctor']:
        records = MedicalRecord.objects.filter(doctor=request_user)
        appointments = Appointment.objects.filter(doctor=request_user)
    else:
        records = MedicalRecord.objects.none()
        appointments = Appointment.objects.none()

    status_filter = (get_params.get('status') or '').strip()
    patient_search = (get_params.get('patient_id') or '').strip()
    date_from = parse_date(get_params.get('date_from')) if get_params.get('date_from') else None
    date_to = parse_date(get_params.get('date_to')) if get_params.get('date_to') else None

    if patient_search and request_user.role in ['staff', 'doctor']:
        patient_q = (
            Q(patient__first_name__icontains=patient_search)
            | Q(patient__last_name__icontains=patient_search)
            | Q(patient__patient_profile__patient_id__icontains=patient_search)
        )
        records = records.filter(patient_q)
        appointments = appointments.filter(patient_q)
    if date_from:
        records = records.filter(created_at__date__gte=date_from)
        appointments = appointments.filter(date__gte=date_from)
    if date_to:
        records = records.filter(created_at__date__lte=date_to)
        appointments = appointments.filter(date__lte=date_to)

    status_totals = {
        'completed': 0,
        'confirmed': 0,
        'cancelled': 0,
        'pending': 0,
        'missed': 0,
    }

    records = (
        records.select_related('patient', 'doctor', 'appointment')
        .prefetch_related('prescription_record__items')
        .order_by('-created_at')
    )
    appointments = appointments.exclude(appointment_type='dental').exclude(
        medicalrecord__isnull=False
    ).select_related('patient', 'doctor').order_by('-date', '-time')

    timeline_rows = []

    for record in records:
        missed_slot = _is_missed_pending_appointment(record.appointment) if record.appointment_id else False
        record_status = record.timeline_filter_status(missed_slot=missed_slot)
        if record_status in status_totals:
            status_totals[record_status] += 1

        local_created_at = timezone.localtime(record.created_at) if timezone.is_aware(record.created_at) else record.created_at
        timeline_rows.append({
            'row_type': 'record',
            'record': record,
            'sort_datetime': local_created_at,
            'missed_slot': missed_slot,
        })

    for appointment in appointments:
        missed_slot = _is_missed_pending_appointment(appointment)
        if missed_slot:
            status_totals['missed'] += 1
        elif appointment.status in status_totals:
            status_totals[appointment.status] += 1

        local_created_at = timezone.localtime(appointment.created_at) if timezone.is_aware(appointment.created_at) else appointment.created_at
        timeline_rows.append({
            'row_type': 'appointment',
            'appointment': appointment,
            'sort_datetime': local_created_at,
            'missed_slot': missed_slot,
        })

    timeline_rows.sort(key=lambda row: row['sort_datetime'], reverse=True)

    if status_filter in _MEDICAL_LIST_STATUS_KEYS:
        timeline_rows = [
            row for row in timeline_rows
            if _effective_timeline_row_status(row) == status_filter
        ]

    return timeline_rows, status_totals


def _build_medical_list_page_context(request):
    get_params = request.GET
    timeline_rows, status_totals = _build_unpaginated_medical_timeline(request.user, get_params)
    records = paginate_queryset(timeline_rows, request)
    list_status = (get_params.get('status') or '').strip()
    return {
        'records': records,
        'total_count': records.paginator.count if records else 0,
        'status_totals': status_totals,
        'list_status': list_status,
        'mr_filter_urls': _medical_list_stat_filter_urls(get_params),
        'mr_stat_active': {key: list_status == key for key in _MEDICAL_LIST_STATUS_KEYS},
        'mr_list_querystring': _medical_list_querystring(get_params),
    }


@login_required
@role_required('student', 'staff', 'doctor')
def medical_records(request):
    """Display medical records based on user role"""
    context = _build_medical_list_page_context(request)
    if is_htmx_request(request):
        return render(request, 'medical_records/_mr_list_filter_oob.html', context)
    return render(request, 'medical_records/medical_records.html', context)


@login_required
@role_required('student', 'staff', 'doctor')
def medical_record_detail_page(request, record_id):
    """View detailed medical record page - similar to dental record detail"""
    record = get_object_or_404(
        MedicalRecord.objects.select_related(
            'patient',
            'patient__patient_profile',
            'doctor',
            'doctor__staff_profile',
            'appointment',
            'prescription_record',
        ).prefetch_related('prescription_record__items'),
        id=record_id,
    )

    # Check permissions
    if is_patient_role(request.user.role) and record.patient != request.user:
        messages.error(request, 'Access denied')
        return redirect('medical_records:medical_records')
    elif request.user.role in ['staff', 'doctor'] and record.doctor != request.user:
        messages.error(request, 'Access denied')
        return redirect('medical_records:medical_records')

    log_clinical_access(
        request,
        action='view',
        resource_type='medical_record',
        resource_id=record.id,
        patient=record.patient,
        resource_label=_medical_record_label(record),
    )

    bc_label = record.patient.get_full_name()
    bc_label += f' — {record.created_at.strftime("%b %d, %Y")}'

    context = {
        'record': record,
        'title': 'Medical Record',
        'breadcrumbs': [
            {'label': 'Medical Records', 'url': reverse('medical_records:medical_records')},
            {'label': bc_label},
        ],
    }

    return render(request, 'medical_records/medical_record_detail.html', context)


@login_required
@role_required('student', 'staff', 'doctor')
def medical_record_detail(request, record_id):
    """AJAX/HTMX view to get medical record details for modal display."""
    record = get_object_or_404(MedicalRecord, id=record_id)
    is_htmx = request.headers.get('HX-Request') == 'true'
    
    # Check permissions
    if is_patient_role(request.user.role) and record.patient != request.user:
        return JsonResponse({'error': 'Access denied'}, status=403) if not is_htmx else HttpResponse('Access denied', status=403)
    elif request.user.role in ['staff', 'doctor'] and record.doctor != request.user:
        return JsonResponse({'error': 'Access denied'}, status=403) if not is_htmx else HttpResponse('Access denied', status=403)
    
    log_clinical_access(
        request,
        action='view',
        resource_type='medical_record',
        resource_id=record.id,
        patient=record.patient,
        resource_label=_medical_record_label(record),
    )

    # Format vital signs for display
    vital_signs_display = []
    if record.vital_signs:
        if record.vital_signs.get('blood_pressure'):
            vital_signs_display.append(f"Blood Pressure: {record.vital_signs['blood_pressure']}")
        if record.vital_signs.get('temperature'):
            vital_signs_display.append(f"Temperature: {record.vital_signs['temperature']}°F")
        if record.vital_signs.get('heart_rate'):
            vital_signs_display.append(f"Heart Rate: {record.vital_signs['heart_rate']} bpm")
        if record.vital_signs.get('weight'):
            vital_signs_display.append(f"Weight: {record.vital_signs['weight']} kg")
    
    html_content = f"""
    <div class="space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
                <h4 class="font-medium text-gray-900 mb-2">Patient Information</h4>
                <div class="bg-gray-50 p-3 rounded-md space-y-1">
                    <p><span class="font-medium">Name:</span> {record.patient.get_full_name()}</p>
                    <p><span class="font-medium">Patient ID:</span> {getattr(record.patient, 'patient_profile', None) and record.patient.patient_profile.patient_id or 'N/A'}</p>
                    <p><span class="font-medium">Date:</span> {record.created_at.strftime('%B %d, %Y at %I:%M %p')}</p>
                </div>
            </div>
            <div>
                <h4 class="font-medium text-gray-900 mb-2">Doctor Information</h4>
                <div class="bg-gray-50 p-3 rounded-md space-y-1">
                    <p><span class="font-medium">Doctor:</span> Dr. {record.doctor.get_full_name()}</p>
                    <p><span class="font-medium">Department:</span> {getattr(record.doctor, 'staff_profile', None) and record.doctor.staff_profile.department or 'N/A'}</p>
                    {f'<p><span class="font-medium">Specialization:</span> {record.doctor.staff_profile.specialization}</p>' if getattr(record.doctor, 'staff_profile', None) and record.doctor.staff_profile.specialization else ''}
                </div>
            </div>
        </div>
        
        <div>
            <h4 class="font-medium text-gray-900 mb-2">Diagnosis</h4>
            <div class="bg-gray-50 p-3 rounded-md">
                <p class="text-gray-800">{record.diagnosis}</p>
            </div>
        </div>
        
        <div>
            <h4 class="font-medium text-gray-900 mb-2">Treatment</h4>
            <div class="bg-gray-50 p-3 rounded-md">
                <p class="text-gray-800">{record.treatment}</p>
            </div>
        </div>
        
        {f'''
        <div>
            <h4 class="font-medium text-gray-900 mb-2">Prescription</h4>
            <div class="bg-gray-50 p-3 rounded-md">
                <p class="text-gray-800">{record.prescription_record.prescription_body if hasattr(record, 'prescription_record') and record.prescription_record else 'No prescription recorded'}</p>
            </div>
        </div>
        ''' if hasattr(record, 'prescription_record') and record.prescription_record else ''}
        
        {f'''
        <div>
            <h4 class="font-medium text-gray-900 mb-2">Vital Signs</h4>
            <div class="bg-gray-50 p-3 rounded-md">
                <ul class="list-disc list-inside space-y-1">
                    {''.join([f'<li class="text-gray-800">{sign}</li>' for sign in vital_signs_display])}
                </ul>
            </div>
        </div>
        ''' if vital_signs_display else ''}
        
        {f'''
        <div>
            <h4 class="font-medium text-gray-900 mb-2">Lab Results</h4>
            <div class="bg-gray-50 p-3 rounded-md">
                <p class="text-gray-800">{record.lab_results}</p>
            </div>
        </div>
        ''' if record.lab_results else ''}
        {f'''
        <div>
            <h4 class="font-medium text-gray-900 mb-2">Related Appointment</h4>
            <div class="bg-gray-50 p-3 rounded-md">
                <p class="text-gray-800">Appointment on {record.appointment.date.strftime("%B %d, %Y")} at {record.appointment.time.strftime("%I:%M %p")}</p>
                <p class="text-sm text-gray-600">Type: {record.appointment.get_appointment_type_display()}</p>
            </div>
        </div>
        ''' if record.appointment else ''}
    </div>
    """
    
    if is_htmx:
        return HttpResponse(html_content)
    return JsonResponse({'html': html_content})


@login_required
def create_medical_record(request, appointment_id):
    if request.user.role not in ['staff', 'doctor']:
        messages.error(request, 'Access denied')
        return redirect('core:dashboard')
    
    appointment = get_object_or_404(Appointment, id=appointment_id, doctor=request.user)

    # General consultation must be confirmed before a medical record can be created.
    if appointment.appointment_type == 'consultation' and appointment.status == 'pending':
        messages.warning(request, 'General consultation appointments must be confirmed first before creating a medical record.')
        return redirect('appointments:appointment_detail', appointment_id=appointment.id)
    
    # Check if medical record already exists
    if MedicalRecord.objects.filter(appointment=appointment).exists():
        messages.warning(request, 'Medical record already exists for this appointment.')
        return redirect('appointments:appointment_detail', appointment_id=appointment.id)

    # Check if dental record already exists for this appointment
    if DentalRecord.objects.filter(appointment=appointment).exists():
        messages.warning(request, 'A dental record already exists for this appointment. Only one record per appointment is allowed.')
        return redirect('appointments:appointment_detail', appointment_id=appointment.id)
    
    prescription_form = _prescription_form_for_request(
        request,
        student=appointment.patient,
        doctor=appointment.doctor,
        acting_user=request.user,
    )
    
    if request.method == 'POST':
        diagnosis = request.POST.get('diagnosis', '').strip()
        treatment = request.POST.get('treatment', '').strip()
        lab_results = request.POST.get('lab_results', '').strip()

        vital_signs, vital_err = _parse_vital_signs_from_post(request.POST)
        if vital_err:
            fk, msg = vital_err
            return _render_create_from_appointment(
                request,
                appointment,
                prescription_form=prescription_form,
                vitals_errors={fk: msg},
            )

        if not diagnosis:
            prescription_form.add_error('diagnosis', 'This field is required.')
        if not treatment:
            prescription_form.add_error(None, 'Treatment rendered is required.')
        if prescription_form.errors:
            return _render_create_from_appointment(request, appointment, prescription_form=prescription_form)

        try:
            with transaction.atomic():
                locked_appointment = Appointment.objects.select_for_update().get(pk=appointment.pk)

                if MedicalRecord.objects.filter(appointment=locked_appointment).exists():
                    messages.warning(request, 'Medical record already exists for this appointment.')
                    return redirect('appointments:appointment_detail', appointment_id=locked_appointment.id)

                if DentalRecord.objects.filter(appointment=locked_appointment).exists():
                    messages.warning(request, 'A dental record already exists for this appointment. Only one record per appointment is allowed.')
                    return redirect('appointments:appointment_detail', appointment_id=locked_appointment.id)

                # Create medical record
                medical_record = MedicalRecord.objects.create(
                    patient=locked_appointment.patient,
                    doctor=request.user,
                    appointment=locked_appointment,
                    diagnosis=diagnosis,
                    treatment=treatment,
                    lab_results=lab_results,
                    vital_signs=vital_signs,
                )

                if request.POST.get('diagnosis', '').strip():
                    _save_prescription_for_medical_record(
                        request,
                        prescription_form,
                        medical_record,
                    )

                # Visit filed: appointment and record completed together
                locked_appointment.status = 'completed'
                locked_appointment.save(update_fields=['status', 'updated_at'])
            
            log_clinical_access(
                request,
                action='create',
                resource_type='medical_record',
                resource_id=medical_record.id,
                patient=medical_record.patient,
                resource_label=_medical_record_label(medical_record),
            )

            # Create notification for student
            notify_user(
                appointment.patient,
                title='Medical Record Created',
                message=f'Your medical record from your appointment on {appointment.date.strftime("%B %d, %Y")} is now available',
                notification_type='general',
                transaction_type='medical_record_created',
                related_id=medical_record.id,
            )
            
            messages.success(request, 'Medical record created successfully!')
            return redirect('appointments:appointment_detail', appointment_id=appointment.id)
            
        except Exception:
            messages.error(request, 'An error occurred while creating the medical record. Please try again.')
            return _render_create_from_appointment(request, appointment, prescription_form=prescription_form)

    return _render_create_from_appointment(request, appointment)


@login_required
@role_required('staff', 'doctor')
def create_medical_record_for_patient(request):
    """Create a medical record for a selected patient without appointment context."""
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        diagnosis = request.POST.get('diagnosis', '').strip()
        treatment = request.POST.get('treatment', '').strip()
        lab_results = request.POST.get('lab_results', '').strip()
        if not patient_id:
            messages.error(request, 'Please select a patient first.')
            return _render_create_for_patient(request, None)

        patient = get_object_or_404(User, id=patient_id, role__in=PATIENT_ROLE_VALUES)
        prescription_form = _prescription_form_for_request(
            request,
            student=patient,
            acting_user=request.user,
        )

        vital_signs, vital_err = _parse_vital_signs_from_post(request.POST)
        if vital_err:
            fk, msg = vital_err
            return _render_create_for_patient(
                request,
                patient,
                prescription_form=prescription_form,
                vitals_errors={fk: msg},
            )

        if not diagnosis:
            prescription_form.add_error('diagnosis', 'This field is required.')
        if not treatment:
            prescription_form.add_error(None, 'Treatment rendered is required.')
        if prescription_form.errors:
            return _render_create_for_patient(request, patient, prescription_form=prescription_form)

        try:
            with transaction.atomic():
                medical_record = MedicalRecord.objects.create(
                    patient=patient,
                    doctor=request.user,
                    appointment=None,
                    diagnosis=diagnosis,
                    treatment=treatment,
                    lab_results=lab_results,
                    vital_signs=vital_signs,
                )

                _save_prescription_for_medical_record(
                    request,
                    prescription_form,
                    medical_record,
                )

            log_clinical_access(
                request,
                action='create',
                resource_type='medical_record',
                resource_id=medical_record.id,
                patient=medical_record.patient,
                resource_label=_medical_record_label(medical_record),
            )

            notify_user(
                patient,
                title='Medical Record Created',
                message='A new medical record has been created for you by the clinic.',
                notification_type='general',
                transaction_type='medical_record_created',
                related_id=medical_record.id,
            )

            messages.success(request, 'Medical record created successfully!')
            return redirect('medical_records:medical_record_detail_page', record_id=medical_record.id)
        except Exception:
            messages.error(request, 'An error occurred while creating the medical record. Please try again.')
            return _render_create_for_patient(request, patient, prescription_form=prescription_form)

    selected_patient = None
    patient_pk = request.GET.get('patient')
    if patient_pk:
        selected_patient = get_object_or_404(User, id=patient_pk, role__in=PATIENT_ROLE_VALUES)

    return _render_create_for_patient(request, selected_patient)
