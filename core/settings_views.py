"""Admin system settings hub and edit views."""

import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme
from .decorators import admin_required
from .htmx_utils import is_htmx_request
from .models import RoleSettings, SettingsChangeLog, User
from .settings_audit import log_form_field_changes
from .settings_forms import (
    ClinicSettingsForm,
    RoleSettingsForm,
    UserPreferencesForm,
    is_valid_settings_role,
)
from .settings_service import get_clinic_settings, get_role_settings, get_user_preferences


def _settings_hub_cards(clinic):
    return [
        {
            'title': 'Clinic settings',
            'description': (
                'Branding, sessions, appointments, maintenance, and sign-in domains.'
            ),
            'url': reverse('core:settings_clinic'),
            'icon': 'fa-hospital',
            'icon_wrap': 'bg-primary-50 text-primary-600',
            'meta': f'{clinic.clinic_name} · {clinic.appointment_interval_minutes} min slots',
        },
        {
            'title': 'Role settings',
            'description': (
                'Session length, profile requirements, and feature access per role.'
            ),
            'url': reverse('core:settings_roles'),
            'icon': 'fa-user-shield',
            'icon_wrap': 'bg-info-50 text-info-600',
            'meta': '4 roles configured',
        },
        {
            'title': 'Academic catalog',
            'description': 'Colleges, courses, and year levels for patient profiles.',
            'url': reverse('core:settings_academic_hub'),
            'icon': 'fa-graduation-cap',
            'icon_wrap': 'bg-success-50 text-success-600',
        },
        {
            'title': 'Audit log',
            'description': 'Review who changed clinic, role, academic, and appointment settings.',
            'url': reverse('core:settings_audit'),
            'icon': 'fa-clock-rotate-left',
            'icon_wrap': 'bg-muted-100 text-muted-600',
        },
        {
            'title': 'Clinical access log',
            'description': 'Review who viewed or changed medical and dental records.',
            'url': reverse('core:clinical_access_log'),
            'icon': 'fa-shield-heart',
            'icon_wrap': 'bg-primary-50 text-primary-600',
        },
        {
            'title': 'Appointment settings',
            'description': 'Assign doctors to each appointment type for student booking.',
            'url': reverse('appointments:appointment_type_settings'),
            'icon': 'fa-calendar-check',
            'icon_wrap': 'bg-success-50 text-success-600',
        },
    ]


def _role_cards():
    cards = []
    for role_value, role_label in User.ROLE.choices:
        settings = get_role_settings(role_value)
        cards.append({
            'role': role_value,
            'label': role_label,
            'session_hours': max(1, settings.session_timeout_seconds // 3600),
            'settings': settings,
        })
    return cards


@login_required
@admin_required
def settings_hub(request):
    clinic = get_clinic_settings()
    return render(
        request,
        'core/settings/hub.html',
        {
            'clinic': clinic,
            'hub_cards': _settings_hub_cards(clinic),
            'role_cards': _role_cards(),
            'settings_subnav_active': 'hub',
        },
    )


@login_required
@admin_required
def settings_clinic(request):
    clinic = get_clinic_settings()

    if request.method == 'POST':
        form = ClinicSettingsForm(request.POST, request.FILES, instance=clinic)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.updated_by = request.user
            obj.save()
            logged = log_form_field_changes(
                actor=request.user,
                setting_type=SettingsChangeLog.SettingType.CLINIC,
                form=form,
            )
            if logged:
                messages.success(request, f'Clinic settings saved ({logged} change(s) logged).')
            else:
                messages.success(request, 'Clinic settings saved.')
            return redirect('core:settings_clinic')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = ClinicSettingsForm(instance=clinic)

    return render(
        request,
        'core/settings/clinic_form.html',
        {
            'form': form,
            'settings_subnav_active': 'clinic',
        },
    )


@login_required
@admin_required
def settings_roles(request):
    return render(
        request,
        'core/settings/roles_list.html',
        {
            'role_cards': _role_cards(),
            'settings_subnav_active': 'roles',
        },
    )


@login_required
@admin_required
def settings_role_edit(request, role):
    if not is_valid_settings_role(role):
        messages.error(request, 'Unknown role.')
        return redirect('core:settings_roles')

    role_settings = get_object_or_404(RoleSettings, role=role)
    role_label = dict(User.ROLE.choices).get(role, role)

    if request.method == 'POST':
        form = RoleSettingsForm(request.POST, instance=role_settings)
        if form.is_valid():
            form.save()
            logged = log_form_field_changes(
                actor=request.user,
                setting_type=SettingsChangeLog.SettingType.ROLE,
                form=form,
                role=role,
            )
            if logged:
                messages.success(request, f'{role_label} settings saved ({logged} change(s) logged).')
            else:
                messages.success(request, f'{role_label} settings saved.')
            return redirect('core:settings_role_edit', role=role)
        messages.error(request, 'Please correct the errors below.')
    else:
        form = RoleSettingsForm(instance=role_settings)

    return render(
        request,
        'core/settings/role_form.html',
        {
            'form': form,
            'role': role,
            'role_label': role_label,
            'settings_subnav_active': 'role',
        },
    )


def _settings_audit_filter_values(request):
    setting_type = (request.GET.get('type') or 'all').strip()
    valid_types = {choice[0] for choice in SettingsChangeLog.SettingType.choices}
    if setting_type not in valid_types:
        setting_type = 'all'
    return {
        'setting_type': setting_type,
        'actor': (request.GET.get('actor') or '').strip(),
        'q': (request.GET.get('q') or '').strip(),
        'date_from': (request.GET.get('date_from') or '').strip(),
        'date_to': (request.GET.get('date_to') or '').strip(),
    }


def _has_active_settings_audit_filters(filter_values):
    return (
        filter_values.get('setting_type') not in ('', 'all')
        or bool(filter_values.get('actor'))
        or bool(filter_values.get('q'))
        or bool(filter_values.get('date_from'))
        or bool(filter_values.get('date_to'))
    )


def _filter_settings_audit_logs(queryset, filter_values):
    setting_type = filter_values['setting_type']
    if setting_type != 'all':
        queryset = queryset.filter(setting_type=setting_type)
    if filter_values['actor']:
        queryset = queryset.filter(changed_by__email__icontains=filter_values['actor'])
    if filter_values['q']:
        query = filter_values['q']
        queryset = queryset.filter(
            Q(field_name__icontains=query)
            | Q(old_value__icontains=query)
            | Q(new_value__icontains=query)
            | Q(role__icontains=query)
        )
    parsed_from = parse_date(filter_values['date_from']) if filter_values['date_from'] else None
    parsed_to = parse_date(filter_values['date_to']) if filter_values['date_to'] else None
    if parsed_from:
        queryset = queryset.filter(created_at__date__gte=parsed_from)
    if parsed_to:
        queryset = queryset.filter(created_at__date__lte=parsed_to)
    return queryset.order_by('-created_at')


def _settings_audit_list_context(request, logs):
    filter_values = _settings_audit_filter_values(request)
    clear_url = reverse('core:settings_audit')
    return {
        'logs': logs,
        'setting_type_choices': SettingsChangeLog.SettingType.choices,
        'filter_url': clear_url,
        'clear_url': clear_url,
        'has_active_filters': _has_active_settings_audit_filters(filter_values),
        'settings_subnav_active': 'audit',
        **filter_values,
    }


def _render_settings_audit_list(request, context):
    if is_htmx_request(request):
        return render(request, 'core/settings/audit_log/_results.html', context)
    return render(request, 'core/settings/audit_log.html', context)


@login_required
@admin_required
def settings_audit(request):
    """Settings change log with live filters and CSV export."""
    filter_values = _settings_audit_filter_values(request)
    logs_qs = _filter_settings_audit_logs(
        SettingsChangeLog.objects.select_related('changed_by'),
        filter_values,
    )

    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="settings-audit-log.csv"'
        writer = csv.writer(response)
        writer.writerow(['When', 'Type', 'Role', 'Field', 'Old', 'New', 'By'])
        for log in logs_qs:
            writer.writerow([
                log.created_at.strftime('%Y-%m-%d %H:%M'),
                log.get_setting_type_display(),
                log.role,
                log.field_name,
                log.old_value,
                log.new_value,
                log.changed_by.email if log.changed_by else '',
            ])
        return response

    context = _settings_audit_list_context(request, logs_qs[:100])
    return _render_settings_audit_list(request, context)


def _preferences_return_url(request):
    """Post-save destination: safe ?next= or profile overview."""
    next_url = (request.POST.get('next') or request.GET.get('next') or '').strip()
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
    ):
        return next_url
    return reverse('core:profile')


@login_required
def profile_preferences(request):
    """Personal notification and UI preferences (all roles)."""
    prefs = get_user_preferences(request.user)
    return_url = _preferences_return_url(request)

    if request.method == 'POST':
        form = UserPreferencesForm(request.POST, instance=prefs)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your preferences were saved.')
            return redirect(_preferences_return_url(request))
        messages.error(request, 'Please correct the errors below.')
    else:
        form = UserPreferencesForm(instance=prefs)

    return render(
        request,
        'core/settings/preferences.html',
        {
            'form': form,
            'return_url': return_url,
        },
    )
