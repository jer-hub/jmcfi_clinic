"""Appointment type settings views (admin only)."""

from collections import defaultdict

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string

from appointments.forms import AppointmentTypeDefaultForm
from appointments.models import Appointment, AppointmentTypeDefault
from core.decorators import admin_required
from core.htmx_utils import is_htmx_request, htmx_add_toast
from core.models import SettingsChangeLog
from core.settings_audit import log_boolean_toggle, log_settings_change, scoped_field_name

from .helpers import _is_json_request

User = get_user_model()


def _doctor_assignment_label(doctors, *, total_doctors=None):
    names = sorted((doctor.get_full_name() or doctor.email) for doctor in doctors)
    if not names:
        return '(none)'
    if total_doctors and len(names) >= total_doctors:
        return '(all active doctors)'
    return ', '.join(names)


def _doctor_pk_set(doctors):
    return {doctor.pk for doctor in doctors}


def _log_appointment_doctor_change(*, actor, default, old_doctors, new_doctors):
    if _doctor_pk_set(old_doctors) == _doctor_pk_set(new_doctors):
        return
    total_doctors = _get_doctors_queryset().count()
    log_settings_change(
        actor=actor,
        setting_type=SettingsChangeLog.SettingType.APPOINTMENT,
        field_name=scoped_field_name(
            default.get_appointment_type_display(),
            'assigned_doctors',
        ),
        old_value=_doctor_assignment_label(old_doctors, total_doctors=total_doctors),
        new_value=_doctor_assignment_label(new_doctors, total_doctors=total_doctors),
    )


def _get_doctors_queryset():
    """Shared queryset for all appointment-type forms — evaluated once per request."""
    return (
        User.objects.filter(role='doctor', is_active=True)
        .select_related('staff_profile')
        .order_by('first_name', 'last_name')
    )


def _doctors_queryset_for_pks(doctor_pks):
    if not doctor_pks:
        return User.objects.none()
    return (
        User.objects.filter(pk__in=doctor_pks)
        .select_related('staff_profile')
        .order_by('first_name', 'last_name')
    )


def _attach_assigned_doctors_cache(instance, assigned_pks, doctors_by_pk):
    if not instance:
        return
    cached = [doctors_by_pk[pk] for pk in assigned_pks if pk in doctors_by_pk]
    instance._prefetched_objects_cache = {
        **getattr(instance, '_prefetched_objects_cache', {}),
        'assigned_doctors': cached,
    }


def _load_appointment_settings_defaults():
    defaults = list(AppointmentTypeDefault.objects.select_related('updated_by').all())
    if not defaults:
        return {}

    through = AppointmentTypeDefault.assigned_doctors.through
    links = through.objects.filter(
        appointmenttypedefault_id__in=[default.pk for default in defaults],
    ).values_list('appointmenttypedefault_id', 'user_id')

    assigned_by_default = defaultdict(list)
    for default_id, user_id in links:
        assigned_by_default[default_id].append(user_id)

    by_type = {}
    for default in defaults:
        assigned_pks = assigned_by_default.get(default.pk, [])
        default._assigned_doctor_pks = assigned_pks
        default._assigned_doctor_count = len(assigned_pks)
        by_type[default.appointment_type] = default
    return by_type


def _prepare_default_for_settings_row(instance, *, doctors_by_pk):
    if not instance or not instance.pk:
        return instance

    assigned_pks = list(
        AppointmentTypeDefault.assigned_doctors.through.objects.filter(
            appointmenttypedefault_id=instance.pk,
        ).values_list('user_id', flat=True)
    )
    instance._assigned_doctor_pks = assigned_pks
    instance._assigned_doctor_count = len(assigned_pks)
    _attach_assigned_doctors_cache(instance, assigned_pks, doctors_by_pk)
    return instance


def _assigned_doctor_count(instance):
    if not instance:
        return 0
    if hasattr(instance, '_assigned_doctor_count'):
        return instance._assigned_doctor_count
    prefetched = getattr(instance, '_prefetched_objects_cache', {}).get('assigned_doctors')
    if prefetched is not None:
        return len(prefetched)
    return AppointmentTypeDefault.assigned_doctors.through.objects.filter(
        appointmenttypedefault_id=instance.pk,
    ).count()


def _build_appointment_settings_item(*, type_key, type_label, instance, doctor_pks, doctor_count):
    form = AppointmentTypeDefaultForm(
        instance=instance,
        initial={'appointment_type': type_key, 'is_active': True} if not instance else {},
        auto_id=f'id_{type_key}_%s',
        doctors_qs=_doctors_queryset_for_pks(doctor_pks),
    )
    assigned_doctor_count = _assigned_doctor_count(instance)
    return {
        'type_key': type_key,
        'type_label': type_label,
        'form': form,
        'instance': instance,
        'doctor_count': doctor_count,
        'assigned_doctor_count': assigned_doctor_count,
        'has_assigned_doctors': assigned_doctor_count > 0,
    }


def _render_appointment_settings_row(*, request, instance, type_label=None):
    doctors = list(_get_doctors_queryset())
    doctors_by_pk = {doctor.pk: doctor for doctor in doctors}
    instance = _prepare_default_for_settings_row(instance, doctors_by_pk=doctors_by_pk)
    item = _build_appointment_settings_item(
        type_key=instance.appointment_type,
        type_label=type_label or instance.get_appointment_type_display(),
        instance=instance,
        doctor_pks=list(doctors_by_pk.keys()),
        doctor_count=len(doctors),
    )
    return render_to_string(
        'appointments/appointment_settings/_settings_row.html',
        {'item': item},
        request=request,
    )


@login_required
@admin_required
def appointment_type_settings(request):
    """
    View for admin to assign doctors to each appointment type via inline forms.
    """
    appointment_types = dict(Appointment.APPOINTMENT_TYPE_CHOICES)
    existing_defaults = _load_appointment_settings_defaults()

    doctors = list(_get_doctors_queryset())
    doctors_by_pk = {doctor.pk: doctor for doctor in doctors}
    doctor_pks = list(doctors_by_pk.keys())
    doctor_count = len(doctors)

    for instance in existing_defaults.values():
        _attach_assigned_doctors_cache(instance, instance._assigned_doctor_pks, doctors_by_pk)

    settings_data = []
    for type_key, type_label in appointment_types.items():
        instance = existing_defaults.get(type_key)
        settings_data.append(
            _build_appointment_settings_item(
                type_key=type_key,
                type_label=type_label,
                instance=instance,
                doctor_pks=doctor_pks,
                doctor_count=doctor_count,
            )
        )

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
            old_doctors = []
            if appointment_default and appointment_default.pk:
                old_doctors = list(appointment_default.assigned_doctors.order_by('pk'))

            with transaction.atomic():
                default = form.save(commit=False)
                default.updated_by = request.user
                default.save()
                form.save_m2m()

                new_doctors = list(default.assigned_doctors.order_by('pk'))
                _log_appointment_doctor_change(
                    actor=request.user,
                    default=default,
                    old_doctors=old_doctors,
                    new_doctors=new_doctors,
                )
            
            type_display = default.get_appointment_type_display()
            
            if is_htmx_request(request):
                default = (
                    AppointmentTypeDefault.objects
                    .select_related('updated_by')
                    .get(pk=default.pk)
                )
                row_html = _render_appointment_settings_row(
                    request=request,
                    instance=default,
                    type_label=type_display,
                )

                response = HttpResponse(row_html)
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
        old_active = default.is_active
        with transaction.atomic():
            default.is_active = not default.is_active
            default.updated_by = request.user
            default.save()
            log_boolean_toggle(
                actor=request.user,
                setting_type=SettingsChangeLog.SettingType.APPOINTMENT,
                scope=default.get_appointment_type_display(),
                field_name='is_active',
                old_value=old_active,
                new_value=default.is_active,
            )

        status = "activated" if default.is_active else "deactivated"
        message_text = f'{default.get_appointment_type_display()} has been {status}.'

        if is_htmx_request(request):
            html = _render_appointment_settings_row(
                request=request,
                instance=default,
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
