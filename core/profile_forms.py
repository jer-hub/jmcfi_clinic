"""Shared helpers for profile edit forms (self-service and admin user edit)."""

from __future__ import annotations

import json

from .academic_catalog import patient_catalog_context
from .forms import StaffProfileForm, StudentProfileForm
from .models import StaffProfile, StudentProfile
from .roles import ROLE_PATIENT, normalize_role, role_matches
from .utils import get_user_profile


def profile_form_class(user):
    """Return ModelForm class for the user's role."""
    if role_matches(user.role, ROLE_PATIENT):
        return StudentProfileForm
    if user.role in ('staff', 'doctor', 'admin'):
        return StaffProfileForm
    raise ValueError(f'Profile editing not available for role {user.role!r}')


def get_or_create_profile(user):
    """Return profile for user, creating a TEMP stub when missing."""
    profile = get_user_profile(user)
    if profile is not None:
        return profile

    role = normalize_role(user.role)
    if role_matches(role, ROLE_PATIENT):
        profile, _ = StudentProfile.objects.get_or_create(
            user=user,
            defaults={
                'patient_id': f'TEMP_{user.id}',
                'phone': '',
                'emergency_contact': '',
                'emergency_phone': '',
                'blood_type': None,
            },
        )
        return profile

    profile, _ = StaffProfile.objects.get_or_create(
        user=user,
        defaults={
            'staff_id': f'TEMP_{user.id}',
            'department': '',
            'phone': '',
        },
    )
    return profile


def instantiate_profile_form(user, profile=None, data=None, files=None, editor=None):
    """Build a profile ModelForm for *user* (staff forms receive user= for role policy)."""
    form_class = profile_form_class(user)
    kwargs = {}
    if profile is not None:
        kwargs['instance'] = profile
    if data is not None:
        kwargs['data'] = data
    if files is not None:
        kwargs['files'] = files
    if role_matches(user.role, ROLE_PATIENT):
        return form_class(**kwargs)
    return form_class(user=user, editor=editor, **kwargs)


def patient_catalog_context_for_form(form, user):
    """Template context fragments for patient college/course/year-level dropdowns."""
    catalog = patient_catalog_context()
    course_options_by_college = json.loads(catalog['course_options_by_college_json'])
    year_level_options_by_college = json.loads(catalog['year_level_options_by_college_json'])

    selected_department = ''
    if form is not None and role_matches(user.role, ROLE_PATIENT) and 'department' in form.fields:
        selected_department = (form['department'].value() or '').strip()

    return {
        'college_options': catalog['college_options'],
        'initial_course_options': course_options_by_college.get(selected_department, []),
        'initial_year_level_options': year_level_options_by_college.get(selected_department, []),
        'college_options_json': catalog['college_options_json'],
        'course_options_by_college_json': catalog['course_options_by_college_json'],
        'year_level_options_by_college_json': catalog['year_level_options_by_college_json'],
        'course_optional_by_college_json': catalog['course_optional_by_college_json'],
    }


def swap_profile_for_role_change(user, old_role):
    """
    Recreate profile stub when admin changes user role.
    Returns True when profile type was swapped.
    """
    if old_role == user.role:
        return False

    if role_matches(old_role, ROLE_PATIENT) and not role_matches(user.role, ROLE_PATIENT):
        if hasattr(user, 'patient_profile'):
            user.patient_profile.delete()
        if not hasattr(user, 'staff_profile'):
            StaffProfile.objects.create(
                user=user,
                staff_id=f'TEMP_{user.id}',
                phone='',
                department='Pending',
            )
    elif role_matches(old_role, 'staff', 'doctor', 'admin') and role_matches(user.role, ROLE_PATIENT):
        if hasattr(user, 'staff_profile'):
            user.staff_profile.delete()
        if not hasattr(user, 'patient_profile'):
            StudentProfile.objects.create(
                user=user,
                patient_id=f'TEMP_{user.id}',
                phone='',
                emergency_contact='',
                emergency_phone='',
                date_of_birth='2000-01-01',
            )
    return True
