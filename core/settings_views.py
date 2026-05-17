"""Admin system settings hub and edit views."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from .decorators import admin_required
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
            'title': 'Audit log',
            'description': 'Review who changed clinic and role settings.',
            'url': reverse('core:settings_audit'),
            'icon': 'fa-clock-rotate-left',
            'icon_wrap': 'bg-muted-100 text-muted-600',
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


@login_required
@admin_required
def settings_audit(request):
    """Recent clinic and role settings changes."""
    logs = (
        SettingsChangeLog.objects.select_related('changed_by')
        .order_by('-created_at')[:100]
    )
    return render(
        request,
        'core/settings/audit_log.html',
        {
            'logs': logs,
            'settings_subnav_active': 'audit',
        },
    )


@login_required
def profile_preferences(request):
    """Personal notification and UI preferences (all roles)."""
    prefs = get_user_preferences(request.user)

    if request.method == 'POST':
        form = UserPreferencesForm(request.POST, instance=prefs)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your preferences were saved.')
            return redirect('core:profile_preferences')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = UserPreferencesForm(instance=prefs)

    return render(
        request,
        'core/settings/preferences.html',
        {
            'form': form,
        },
    )
