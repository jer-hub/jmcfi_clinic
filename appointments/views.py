from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.template.loader import render_to_string
from django.test import RequestFactory
from urllib.parse import urlencode, urlparse
from django.http import QueryDict
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib.auth import get_user_model
from django.db.models import Q
import json

from .models import Appointment, AppointmentTypeDefault
from .forms import AppointmentTypeDefaultForm
from .appointment_utils import check_appointment_availability, format_conflict_message
from .calendar_service import (
    CalendarFilters,
    build_calendar_context,
    build_calendar_page_url,
    build_ics_calendar,
    parse_calendar_filters,
)
from core.access_control import AccessReason, access_denied_response
from core.clinical_permissions import can_write_appointments
from core.decorators import role_required, admin_required
from core.roles import PATIENT_ROLE_VALUES, ROLE_DOCTOR, ROLE_PATIENT, ROLE_STAFF, role_matches
from core.settings_service import get_clinic_settings
from core.notification_delivery import notify_user
from core.htmx_utils import is_htmx_request, htmx_add_toast, htmx_add_trigger


def _is_json_request(request):
    content_type = (request.content_type or '').lower()
    return content_type.startswith('application/json')

User = get_user_model()


def paginate_queryset(queryset, request, per_page=10):
    """Helper function for pagination"""
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    
    page = request.GET.get('page', 1)
    paginator = Paginator(queryset, per_page)
    
    try:
        paginated_items = paginator.page(page)
    except PageNotAnInteger:
        paginated_items = paginator.page(1)
    except EmptyPage:
        paginated_items = paginator.page(paginator.num_pages)
    
    return paginated_items


def _effective_appointment_list_get_params(request):
    """List filters for HTMX OOB: prefer HX-Current-URL query, then Referer query, then GET."""
    for header_name in ('HX-Current-URL', 'Referer'):
        raw = (request.headers.get(header_name) or '').strip()
        if raw:
            q = urlparse(raw).query
            if q:
                return QueryDict(q)
    return request.GET


def _appointment_list_request_path_matches(url: str) -> bool:
    if not (url or '').strip():
        return False
    list_path = reverse('appointments:appointment_list').rstrip('/')
    path = urlparse(url).path.rstrip('/')
    return path == list_path


def _is_appointment_list_htmx_context(request):
    if _appointment_list_request_path_matches(request.headers.get('HX-Current-URL') or ''):
        return True
    return _appointment_list_request_path_matches(request.headers.get('Referer') or '')


def _appointment_list_request_for_params(original_request, get_params: QueryDict):
    """Build a GET request carrying list filters (pagination + table partial)."""
    rf = RequestFactory()
    path = reverse('appointments:appointment_list')
    list_req = rf.get(
        path,
        data=get_params.dict(),
        HTTP_HOST=original_request.get_host(),
        secure=original_request.is_secure(),
    )
    list_req.user = original_request.user
    return list_req


def _appointment_list_querystring(get_params: QueryDict) -> str:
    q = get_params.copy()
    q.pop('page', None)
    encoded = q.urlencode()
    return f'&{encoded}' if encoded else ''


_APPOINTMENT_LIST_STATUS_KEYS = ('pending', 'confirmed', 'completed', 'missed', 'cancelled')


def _appointment_list_stat_filter_url(get_params: QueryDict, status_key: str) -> str:
    """Toggle *status_key* in list query string; preserve other filters."""
    q = get_params.copy()
    current = (q.get('status') or '').strip()
    if current == status_key:
        q.pop('status', None)
    else:
        q['status'] = status_key
    q.pop('page', None)
    base = reverse('appointments:appointment_list')
    encoded = q.urlencode()
    return f'{base}?{encoded}' if encoded else base


def _appointment_list_stat_filter_urls(get_params: QueryDict) -> dict[str, str]:
    return {key: _appointment_list_stat_filter_url(get_params, key) for key in _APPOINTMENT_LIST_STATUS_KEYS}


def _appointment_list_base_queryset(user):
    if role_matches(user.role, ROLE_PATIENT):
        return Appointment.objects.filter(patient=user)
    if user.role == ROLE_DOCTOR:
        return Appointment.objects.filter(doctor=user)
    if user.role == ROLE_STAFF:
        return Appointment.objects.all()
    if user.role == 'admin':
        return Appointment.objects.all()
    return Appointment.objects.none()


def _apply_appointment_list_filters(queryset, get_params, user, *, apply_status_filter=True):
    status = get_params.get('status')
    date_from_str = get_params.get('date_from')
    date_to_str = get_params.get('date_to')
    doctor_id = get_params.get('doctor')
    appointment_type = get_params.get('appointment_type')
    patient_search = (get_params.get('patient_search') or '').strip()

    if apply_status_filter and status:
        queryset = queryset.filter(status=status)
    if date_from_str:
        date_from = parse_date(date_from_str)
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
    if date_to_str:
        date_to = parse_date(date_to_str)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
    if doctor_id:
        queryset = queryset.filter(doctor_id=doctor_id)
    if appointment_type:
        queryset = queryset.filter(appointment_type=appointment_type)
    if patient_search and user.role in ['doctor', 'staff']:
        queryset = queryset.filter(
            Q(patient__first_name__icontains=patient_search)
            | Q(patient__last_name__icontains=patient_search)
            | Q(patient__patient_profile__patient_id__icontains=patient_search)
        )

    current_filters = {
        'status': status,
        'date_from': date_from_str,
        'date_to': date_to_str,
        'doctor': int(doctor_id) if doctor_id else None,
        'appointment_type': appointment_type,
        'patient_search': patient_search,
    }
    return queryset, current_filters


def _appointment_list_status_totals(queryset):
    return {
        'pending': queryset.filter(status='pending').count(),
        'confirmed': queryset.filter(status='confirmed').count(),
        'completed': queryset.filter(status='completed').count(),
        'missed': queryset.filter(status='missed').count(),
        'cancelled': queryset.filter(status='cancelled').count(),
    }


def _build_appointment_list_context(user, get_params, list_request):
    base_qs = _appointment_list_base_queryset(user)
    qs_for_totals, _ = _apply_appointment_list_filters(
        base_qs, get_params, user, apply_status_filter=False
    )
    status_totals = _appointment_list_status_totals(qs_for_totals)
    appointments_qs, current_filters = _apply_appointment_list_filters(
        base_qs, get_params, user, apply_status_filter=True
    )
    appointments_qs = (
        appointments_qs.select_related('patient', 'doctor', 'patient__patient_profile')
        .prefetch_related('dental_records', 'medicalrecord_set')
        .order_by('-created_at')
    )
    paginated = paginate_queryset(appointments_qs, list_request)
    list_status = (get_params.get('status') or '').strip()
    return {
        'appointments': paginated,
        'total_count': paginated.paginator.count if paginated else 0,
        'status_totals': status_totals,
        'doctors': User.objects.filter(role='doctor').order_by('first_name', 'last_name'),
        'appointment_types': Appointment.APPOINTMENT_TYPE_CHOICES,
        'current_filters': current_filters,
        'appt_list_querystring': _appointment_list_querystring(get_params),
        'appt_filter_urls': _appointment_list_stat_filter_urls(get_params),
        'appt_stat_active': {key: list_status == key for key in _APPOINTMENT_LIST_STATUS_KEYS},
    }


def _appointment_list_htmx_oob_response(request, message, toast_type='success'):
    get_params = _effective_appointment_list_get_params(request)
    list_req = _appointment_list_request_for_params(request, get_params)
    ctx = _build_appointment_list_context(request.user, get_params, list_req)
    oob_html = render_to_string(
        'appointments/_appt_post_status_oob.html',
        {
            'status_totals': ctx['status_totals'],
            'total_count': ctx['total_count'],
            'appt_filter_urls': ctx['appt_filter_urls'],
            'appt_stat_active': ctx['appt_stat_active'],
            'list_table_appointments': ctx['appointments'],
            'list_table_request': list_req,
            'appt_list_querystring': ctx['appt_list_querystring'],
            'user': request.user,
        },
        request=request,
    )
    response = HttpResponse(oob_html, status=200)
    response = htmx_add_trigger(response, 'close-modal')
    return htmx_add_toast(response, message, toast_type)


@login_required
@role_required('student', 'staff', 'doctor')
def appointment_list(request):
    """Display list of appointments based on user role"""
    context = _build_appointment_list_context(request.user, request.GET, request)
    if is_htmx_request(request):
        return render(request, 'appointments/_appt_list_filter_oob.html', context)
    return render(request, 'appointments/appointment_list.html', context)


def _calendar_filters_from_request(request, *, full_page: bool = False):
    filters = parse_calendar_filters(request.GET, request.user, full_page=full_page)
    if full_page or request.GET.get('full') == '1':
        filters = CalendarFilters(
            year=filters.year,
            month=filters.month,
            selected_date=filters.selected_date,
            doctor_id=filters.doctor_id,
            status_filter=filters.status_filter,
            event_filter=filters.event_filter,
            full_page=True,
            view_mode=filters.view_mode,
        )
    return filters


def _calendar_htmx_response(request, template, context, filters):
    response = render(request, template, context)
    if filters.full_page:
        response['HX-Push-Url'] = build_calendar_page_url(filters)
    return response


@login_required
@role_required('student', 'staff', 'doctor')
def appointment_calendar(request):
    """Full-page appointment calendar."""
    filters = _calendar_filters_from_request(request, full_page=True)
    context = build_calendar_context(request.user, filters)
    context['calendar_embedded'] = False
    return render(request, 'appointments/calendar.html', context)


@login_required
@role_required('student', 'staff', 'doctor')
def calendar_body_fragment(request):
    """HTMX: month/week grid + day panel refresh."""
    filters = _calendar_filters_from_request(request)
    context = build_calendar_context(request.user, filters)
    return _calendar_htmx_response(
        request,
        'components/calendar/_calendar_body.html',
        context,
        filters,
    )


# Backward-compatible name for bookmarks/tests
calendar_month_fragment = calendar_body_fragment


@login_required
@role_required('student', 'staff', 'doctor')
def calendar_export_ics(request):
    """Download ICS for visible calendar range."""
    filters = _calendar_filters_from_request(request)
    ics_body = build_ics_calendar(request.user, filters)
    response = HttpResponse(ics_body, content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="clinic-schedule.ics"'
    return response


@login_required
@role_required('student', 'staff', 'doctor')
def calendar_day_fragment(request):
    """HTMX: day agenda panel."""
    filters = _calendar_filters_from_request(request)
    context = build_calendar_context(request.user, filters)
    return _calendar_htmx_response(
        request,
        'components/calendar/_day_agenda.html',
        context,
        filters,
    )


@login_required
def schedule_appointment(request):
    if not role_matches(request.user.role, ROLE_PATIENT):
        messages.error(request, 'Only patients can schedule appointments')
        return redirect('core:dashboard')

    form_data = {}

    if request.method == 'POST':
        doctor_id = request.POST.get('doctor')
        appointment_type = request.POST.get('appointment_type')
        date = request.POST.get('date')
        time = request.POST.get('time')
        reason = request.POST.get('reason', '').strip()

        form_data = {
            'doctor': doctor_id or '',
            'appointment_type': appointment_type or '',
            'date': date or '',
            'time': time or '',
            'reason': reason,
        }

        if not all([doctor_id, appointment_type, date, time, reason]):
            messages.error(request, 'All fields are required.')
            return render(request, 'appointments/schedule_appointment.html',
                          _get_schedule_context(form_data=form_data))

        try:
            from datetime import datetime
            appointment_date = datetime.strptime(date, '%Y-%m-%d').date()
            appointment_time = datetime.strptime(time, '%H:%M').time()

            if appointment_date < timezone.now().date():
                messages.error(request, 'Cannot schedule appointments for past dates.')
                return render(request, 'appointments/schedule_appointment.html',
                              _get_schedule_context(form_data=form_data))

            max_days = get_clinic_settings().max_advance_booking_days
            from datetime import timedelta

            latest_date = timezone.now().date() + timedelta(days=max_days)
            if appointment_date > latest_date:
                messages.error(
                    request,
                    f'Appointments can only be booked up to {max_days} days in advance.',
                )
                return render(request, 'appointments/schedule_appointment.html',
                              _get_schedule_context(form_data=form_data))

            if appointment_date.weekday() >= 5:
                messages.error(request, 'Appointments are not available on weekends.')
                return render(request, 'appointments/schedule_appointment.html',
                              _get_schedule_context(form_data=form_data))

            doctor = User.objects.get(id=doctor_id, role='doctor', is_active=True)

            type_default = AppointmentTypeDefault.objects.filter(
                appointment_type=appointment_type, is_active=True
            ).prefetch_related('assigned_doctors').first()
            if not type_default:
                if AppointmentTypeDefault.objects.filter(appointment_type=appointment_type).exists():
                    messages.error(request, 'This appointment type is currently inactive.')
                else:
                    messages.error(request, 'Invalid appointment type selected.')
                return render(request, 'appointments/schedule_appointment.html',
                              _get_schedule_context(form_data=form_data))

            is_valid, err_msg = _validate_assigned_doctor_for_type(doctor, appointment_type)
            if not is_valid:
                messages.error(request, err_msg)
                return render(request, 'appointments/schedule_appointment.html',
                              _get_schedule_context(form_data=form_data))

            is_available, conflicts = check_appointment_availability(doctor, appointment_date, appointment_time)

            if not is_available:
                conflict_msg = format_conflict_message(doctor, conflicts)
                messages.error(request, conflict_msg)
                return render(request, 'appointments/schedule_appointment.html',
                              _get_schedule_context(form_data=form_data))

            appointment = Appointment.objects.create(
                patient=request.user,
                doctor=doctor,
                appointment_type=appointment_type,
                date=appointment_date,
                time=appointment_time,
                reason=reason
            )

            notify_user(
                doctor,
                title='New Appointment Request',
                message=(
                    f'New appointment request from {request.user.get_full_name()} for '
                    f'{appointment_date.strftime("%B %d, %Y")} at {appointment_time.strftime("%I:%M %p")}'
                ),
                notification_type='appointment',
                transaction_type='appointment_scheduled',
                related_id=appointment.id,
            )

            messages.success(request, 'Appointment scheduled successfully!')
            return redirect('appointments:appointment_list')

        except User.DoesNotExist:
            messages.error(request, 'Invalid doctor selected.')
        except ValueError:
            messages.error(request, 'Invalid date or time format.')
        except Exception:
            messages.error(request, 'An error occurred while scheduling the appointment. Please try again.')

        return render(request, 'appointments/schedule_appointment.html',
                      _get_schedule_context(form_data=form_data))

    initial_form: dict[str, str] = {}
    prefill_date = parse_date(request.GET.get('date', ''))
    if prefill_date:
        initial_form['date'] = prefill_date.isoformat()
    return render(request, 'appointments/schedule_appointment.html', _get_schedule_context(form_data=initial_form))


def _get_schedule_context(form_data=None, *, doctors_only=False):
    """
    Build doctor/type picker context for scheduling forms.
    When doctors_only is True, only users with role=doctor are included (staff booking).
    """
    active_defaults = (
        AppointmentTypeDefault.objects
        .filter(is_active=True)
        .prefetch_related('assigned_doctors')
        .order_by('appointment_type')
    )

    role_filter = ['doctor'] if doctors_only else ['staff', 'doctor']

    type_doctor_map = {}
    all_assigned_ids = set()

    for default in active_defaults:
        assigned = list(
            default.assigned_doctors.filter(role__in=role_filter, is_active=True).values_list('id', flat=True)
        )
        type_doctor_map[default.appointment_type] = assigned
        all_assigned_ids.update(assigned)

    doctors = User.objects.filter(
        id__in=all_assigned_ids, role__in=role_filter, is_active=True
    ).select_related('staff_profile').order_by('first_name', 'last_name')

    doctors_payload = []
    for doctor in doctors:
        name = doctor.get_full_name() or doctor.email or ''
        spec = ''
        dept = ''
        if getattr(doctor, 'staff_profile', None):
            if doctor.staff_profile.specialization:
                spec = f' - {doctor.staff_profile.specialization}'
            if doctor.staff_profile.department:
                dept = f' ({doctor.staff_profile.department})'
        doctors_payload.append(
            {
                'id': str(doctor.id),
                'name': f'Dr. {name}{spec}{dept}',
            }
        )

    fd = form_data or {}
    return {
        'doctors': doctors,
        'doctors_json': json.dumps(doctors_payload),
        'active_defaults': active_defaults,
        'type_doctor_map': json.dumps(type_doctor_map),
        'form_data': fd,
        'form_data_json': json.dumps(fd),
    }


def _validate_assigned_doctor_for_type(doctor, appointment_type):
    """
    Return (is_valid, error_message) for doctor/type assignment.
    doctor must be a User instance; appointment_type is the choice key.
    """
    type_default = AppointmentTypeDefault.objects.filter(
        appointment_type=appointment_type, is_active=True
    ).prefetch_related('assigned_doctors').first()
    if not type_default:
        if AppointmentTypeDefault.objects.filter(appointment_type=appointment_type).exists():
            return False, 'This appointment type is currently inactive.'
        return False, 'Invalid appointment type selected.'

    allowed_ids = list(
        type_default.assigned_doctors.filter(
            role__in=['staff', 'doctor'], is_active=True
        ).values_list('id', flat=True)
    )
    if not allowed_ids:
        return False, 'No doctors are available for this appointment type. Please contact the clinic.'
    if doctor.id not in allowed_ids:
        return False, 'The selected doctor is not available for this appointment type.'
    return True, ''


@login_required
@role_required('student', 'staff', 'doctor', 'admin')
def appointment_detail(request, appointment_id):
    appointment = get_object_or_404(
        Appointment.objects.select_related('patient', 'doctor').prefetch_related('dental_records', 'medicalrecord_set'),
        id=appointment_id,
    )
    
    # Check permissions (admin can view all)
    if role_matches(request.user.role, ROLE_PATIENT) and appointment.patient != request.user:
        messages.error(request, 'Access denied')
        return redirect('appointments:appointment_list')
    elif request.user.role == ROLE_DOCTOR and appointment.doctor != request.user:
        messages.error(request, 'Access denied')
        return redirect('appointments:appointment_list')
    
    if request.method == 'POST':
        next_url = request.POST.get('next')
        is_htmx = is_htmx_request(request)
        list_htmx = is_htmx and (
            request.POST.get('htmx_from_appt_list') == '1' or _is_appointment_list_htmx_context(request)
        )

        def htmx_error(message, status_code=400):
            if list_htmx:
                response = HttpResponse('', status=status_code)
                return htmx_add_toast(response, message, 'error')
            if is_htmx:
                response = HttpResponse('', status=status_code)
                return htmx_add_toast(response, message, 'error')
            messages.error(request, message)
            return None

        success_message = None

        if can_write_appointments(request.user, appointment):
            status = request.POST.get('status')
            notes = request.POST.get('notes')
            previous_status = appointment.status

            if previous_status == 'cancelled':
                if status and status != 'cancelled':
                    err = htmx_error('Cancelled appointments cannot be changed.')
                    if err:
                        return err
                if notes is not None:
                    appointment.notes = notes
                    appointment.save(update_fields=['notes', 'updated_at'])
                    success_message = 'Notes updated.'
            else:
                if status:
                    appointment.status = status
                if notes is not None:
                    appointment.notes = notes
                appointment.save()

                if status and appointment.status != previous_status:
                    status_to_transaction = {
                        'pending': 'appointment_reminder',
                        'confirmed': 'appointment_confirmed',
                        'completed': 'appointment_completed',
                        'missed': 'appointment_reminder',
                        'cancelled': 'appointment_cancelled',
                    }
                    notify_user(
                        appointment.patient,
                        title='Appointment Update',
                        message=f'Your appointment status has been updated to {appointment.get_status_display()}',
                        notification_type='appointment',
                        transaction_type=status_to_transaction.get(appointment.status, 'appointment_reminder'),
                        related_id=appointment.id,
                    )

                success_message = f'Appointment updated to {appointment.get_status_display()}.'

        elif role_matches(request.user.role, ROLE_PATIENT) and appointment.patient == request.user:
            status = request.POST.get('status')
            if status == 'cancelled' and appointment.status in ['pending']:
                from datetime import datetime as dt

                cutoff_hours = get_clinic_settings().cancellation_cutoff_hours
                appt_start = timezone.make_aware(
                    dt.combine(appointment.date, appointment.time),
                    timezone.get_current_timezone(),
                )
                from datetime import timedelta

                if timezone.now() + timedelta(hours=cutoff_hours) > appt_start:
                    err = htmx_error(
                        f'Cancellations must be at least {cutoff_hours} hours before the appointment.',
                    )
                    if err:
                        return err

                appointment.status = 'cancelled'
                appointment.save()

                notify_user(
                    appointment.doctor,
                    title='Appointment Cancelled',
                    message=f'Appointment with {request.user.get_full_name()} has been cancelled',
                    notification_type='appointment',
                    transaction_type='appointment_cancelled',
                    related_id=appointment.id,
                )

                success_message = 'Appointment cancelled successfully!'
            else:
                err = htmx_error('Cannot cancel this appointment')
                if err:
                    return err
        else:
            err = htmx_error('Access denied', status_code=403)
            if err:
                return err
            return access_denied_response(request, status_code=403, reason=AccessReason.FORBIDDEN)

        if list_htmx and success_message:
            return _appointment_list_htmx_oob_response(request, success_message)

        if success_message:
            messages.success(request, success_message)

        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)

        return redirect('appointments:appointment_detail', appointment_id=appointment.id)
    
    from django.urls import reverse

    breadcrumbs = [
        {'label': 'Appointments', 'url': reverse('appointments:appointment_list')},
        {'label': f'{appointment.patient.get_full_name()} — {appointment.date.strftime("%b %d, %Y")}'},
    ]
    return render(request, 'appointments/appointment_detail.html', {
        'appointment': appointment,
        'breadcrumbs': breadcrumbs,
    })


# ============================================================================
# Appointment Settings Views (Admin Only)
# ============================================================================

def _get_doctors_queryset():
    """Shared queryset for all appointment-type forms — evaluated once per request."""
    return (
        User.objects.filter(role__in=['doctor', 'staff'], is_active=True)
        .select_related('staff_profile')
        .order_by('first_name', 'last_name')
    )


@login_required
@admin_required
def appointment_type_settings(request):
    """
    View for admin to assign doctors to each appointment type via inline forms.
    """
    appointment_types = dict(Appointment.APPOINTMENT_TYPE_CHOICES)
    existing_defaults = {
        d.appointment_type: d
        for d in AppointmentTypeDefault.objects.prefetch_related('assigned_doctors').all()
    }

    doctors_qs = _get_doctors_queryset()

    settings_data = []
    for type_key, type_label in appointment_types.items():
        instance = existing_defaults.get(type_key)
        initial = {'appointment_type': type_key, 'is_active': True} if not instance else {}
        form = AppointmentTypeDefaultForm(
            instance=instance, initial=initial,
            auto_id=f'id_{type_key}_%s', doctors_qs=doctors_qs,
        )
        settings_data.append({
            'type_key': type_key,
            'type_label': type_label,
            'form': form,
            'instance': instance,
        })

    return render(request, 'appointments/appointment_settings/appointment_type_settings.html', {
        'settings_subnav_active': 'appointments',
        'settings_data': settings_data,
    })


@login_required
@admin_required
def edit_appointment_type_default(request, type_key=None):
    """
    Handle form submission for inline doctor assignment editing.
    GET requests redirect to the settings page (no separate edit page).
    POST requests process the form and redirect back to settings.
    """
    # For GET requests, redirect to settings page (consolidate to inline edit only)
    if request.method == 'GET':
        return redirect('appointments:appointment_type_settings')
    
    # Handle POST form submissions from inline dropdown
    if request.method == 'POST':
        # Try to get existing default or create new
        if type_key:
            appointment_default = AppointmentTypeDefault.objects.filter(appointment_type=type_key).first()
        else:
            appointment_default = None
        
        form = AppointmentTypeDefaultForm(request.POST, instance=appointment_default)
        if form.is_valid():
            default = form.save(commit=False)
            default.updated_by = request.user
            default.save()
            form.save_m2m()
            
            type_display = default.get_appointment_type_display()
            
            if is_htmx_request(request):
                from django.template.loader import render_to_string

                default = (
                    AppointmentTypeDefault.objects
                    .prefetch_related('assigned_doctors')
                    .select_related('updated_by')
                    .get(pk=default.pk)
                )
                badge_html = render_to_string(
                    'appointments/appointment_settings/_status_badge.html',
                    {'instance': default},
                    request=request,
                )
                
                response = HttpResponse(badge_html)
                return htmx_add_toast(response, f'Doctor assignments saved for {type_display}.')
            
            messages.success(
                request,
                f'Successfully updated doctor assignments for {type_display}.'
            )
        else:
            if is_htmx_request(request):
                response = JsonResponse({
                    'success': False,
                    'errors': form.errors,
                }, status=400)
                return htmx_add_toast(response, 'Please correct the errors in the form.', 'error')
            
            messages.error(request, 'Please correct the errors below.')
    
    return redirect('appointments:appointment_type_settings')


@login_required
@admin_required
def toggle_appointment_type_default(request, default_id):
    """
    Quick toggle for activating/deactivating an appointment type default.
    Supports both HTMX and traditional AJAX requests.
    """
    if request.method == 'POST':
        default = get_object_or_404(AppointmentTypeDefault, id=default_id)
        default.is_active = not default.is_active
        default.updated_by = request.user
        default.save()
        
        status = "activated" if default.is_active else "deactivated"
        message_text = f'{default.get_appointment_type_display()} has been {status}.'

        if is_htmx_request(request):
            from django.template.loader import render_to_string

            doctors_qs = _get_doctors_queryset()
            form = AppointmentTypeDefaultForm(
                instance=default, auto_id=f'id_{default.appointment_type}_%s',
                doctors_qs=doctors_qs,
            )
            item = {
                'type_key': default.appointment_type,
                'type_label': default.get_appointment_type_display(),
                'form': form,
                'instance': default,
            }
            html = render_to_string(
                'appointments/appointment_settings/_settings_row.html',
                {'item': item}, request=request,
            )
            response = HttpResponse(html)
            return htmx_add_toast(response, message_text)
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or _is_json_request(request):
            return JsonResponse({
                'success': True,
                'is_active': default.is_active,
                'message': message_text,
            })

        messages.success(request, message_text)

    return redirect('appointments:appointment_type_settings')


def _patient_prefill_payload(patient):
    """JSON-serializable patient row for schedule-for-patient Alpine prefill."""
    from core.utils import student_display_name

    profile = getattr(patient, 'patient_profile', None)
    patient_id = getattr(profile, 'patient_id', '') or ''
    return {
        'id': patient.id,
        'name': student_display_name(patient),
        'email': patient.email or '',
        'patient_id': patient_id,
        'course': getattr(profile, 'course', '') or '',
        'year_level': str(getattr(profile, 'year_level', '') or ''),
    }


def _schedule_for_patient_redirect(patient_id=None):
    base = reverse('appointments:schedule_for_patient')
    if patient_id:
        return redirect(f'{base}?{urlencode({"patient": patient_id})}')
    return redirect(base)


def _schedule_for_patient_get_context(request, patient_id_hint=None, form_data=None):
    active_type_keys = set(
        AppointmentTypeDefault.objects
        .filter(is_active=True)
        .values_list('appointment_type', flat=True)
    )
    if active_type_keys:
        appointment_types = [
            (key, label)
            for key, label in Appointment.APPOINTMENT_TYPE_CHOICES
            if key in active_type_keys
        ]
    else:
        appointment_types = Appointment.APPOINTMENT_TYPE_CHOICES

    prefill_patient = None
    prefill_invalid = False
    param = patient_id_hint if patient_id_hint is not None else request.GET.get('patient')
    if param:
        try:
            patient = User.objects.select_related('patient_profile').get(
                pk=int(param),
                role__in=PATIENT_ROLE_VALUES,
            )
            prefill_patient = _patient_prefill_payload(patient)
        except (User.DoesNotExist, ValueError, TypeError):
            prefill_invalid = True

    fd = form_data or {}
    context = {
        'appointment_types': appointment_types,
        'prefill_patient': prefill_patient,
        'prefill_invalid': prefill_invalid,
        'patient_locked': prefill_patient is not None,
        'staff_picks_doctor': request.user.role == ROLE_STAFF,
        'form_data': fd,
        'form_data_json': json.dumps(fd),
    }
    if request.user.role == ROLE_STAFF:
        context.update(_get_schedule_context(form_data=form_data, doctors_only=True))
    return context


def _render_schedule_for_patient(request, patient_id_hint=None, form_data=None):
    context = _schedule_for_patient_get_context(request, patient_id_hint=patient_id_hint, form_data=form_data)
    return render(request, 'appointments/schedule_for_patient.html', context)


@login_required
@role_required('doctor', 'staff', 'admin')
def schedule_for_patient(request):
    """Allows staff and doctors to schedule an appointment for a patient."""
    staff_picks_doctor = request.user.role == ROLE_STAFF

    if request.method == 'POST':
        patient_id = request.POST.get('patient')
        appointment_type = request.POST.get('appointment_type')
        date_str = request.POST.get('date')
        time_str = request.POST.get('time')
        reason = request.POST.get('reason')
        doctor_id = request.POST.get('doctor') if staff_picks_doctor else None

        form_data = {
            'patient': patient_id or '',
            'appointment_type': appointment_type or '',
            'date': date_str or '',
            'time': time_str or '',
            'reason': reason or '',
            'doctor': doctor_id or '',
        }

        required = [patient_id, appointment_type, date_str, time_str, reason]
        if staff_picks_doctor:
            required.append(doctor_id)

        if not all(required):
            messages.error(request, 'All fields are required.')
            return _render_schedule_for_patient(request, patient_id_hint=patient_id, form_data=form_data)

        try:
            patient = User.objects.get(id=patient_id, role__in=PATIENT_ROLE_VALUES)
            if staff_picks_doctor:
                doctor = User.objects.get(id=doctor_id, role=ROLE_DOCTOR, is_active=True)
            else:
                doctor = request.user
            from datetime import datetime
            appointment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            appointment_time = datetime.strptime(time_str, '%H:%M').time()

            if appointment_date < timezone.now().date():
                messages.error(request, 'Cannot schedule appointments for past dates.')
                return _render_schedule_for_patient(request, patient_id_hint=patient_id, form_data=form_data)

            if appointment_date.weekday() >= 5:
                messages.error(request, 'Appointments are not available on weekends.')
                return _render_schedule_for_patient(request, patient_id_hint=patient_id, form_data=form_data)

            if staff_picks_doctor:
                is_valid, err_msg = _validate_assigned_doctor_for_type(doctor, appointment_type)
                if not is_valid:
                    messages.error(request, err_msg)
                    return _render_schedule_for_patient(request, patient_id_hint=patient_id, form_data=form_data)
            else:
                type_default = AppointmentTypeDefault.objects.filter(
                    appointment_type=appointment_type, is_active=True
                ).first()
                if not type_default and AppointmentTypeDefault.objects.filter(appointment_type=appointment_type).exists():
                    messages.error(request, 'This appointment type is currently inactive.')
                    return _render_schedule_for_patient(request, patient_id_hint=patient_id, form_data=form_data)

            is_available, conflicts = check_appointment_availability(doctor, appointment_date, appointment_time)
            if not is_available:
                conflict_msg = format_conflict_message(doctor, conflicts)
                messages.error(request, conflict_msg)
                return _render_schedule_for_patient(request, patient_id_hint=patient_id, form_data=form_data)

            patient_conflict = Appointment.objects.filter(
                patient=patient,
                date=appointment_date,
                time=appointment_time,
                status__in=['pending', 'confirmed']
            ).exists()
            if patient_conflict:
                messages.error(request, f'{patient.get_full_name()} already has a pending or confirmed appointment at this time.')
                return _render_schedule_for_patient(request, patient_id_hint=patient_id, form_data=form_data)

            appointment = Appointment.objects.create(
                patient=patient,
                doctor=doctor,
                appointment_type=appointment_type,
                date=appointment_date,
                time=appointment_time,
                reason=reason,
                status='confirmed',
            )

            notify_user(
                patient,
                title='Appointment Scheduled for You',
                message=(
                    f'Dr. {doctor.get_full_name()} has scheduled a new appointment for you on '
                    f'{appointment_date.strftime("%B %d, %Y")} at {appointment_time.strftime("%I:%M %p")}.'
                ),
                notification_type='appointment',
                transaction_type='appointment_scheduled',
                related_id=appointment.id,
            )

            messages.success(request, f'Appointment successfully scheduled for {patient.get_full_name()}.')
            return redirect('appointments:appointment_list')

        except User.DoesNotExist:
            messages.error(request, 'Invalid patient or doctor selected.')
        except ValueError:
            messages.error(request, 'Invalid date or time format.')
        except Exception as e:
            messages.error(request, f'An error occurred: {e}')

        return _render_schedule_for_patient(request, patient_id_hint=request.POST.get('patient'), form_data=form_data)

    return _render_schedule_for_patient(request)
