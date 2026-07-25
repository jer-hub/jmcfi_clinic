"""Shared helpers for profile edit forms (self-service and admin user edit)."""

from __future__ import annotations

import json
import uuid

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


def _profile_image_name(profile):
    image = getattr(profile, 'profile_image', None)
    return image.name if image else ''


def _clear_profile_image_without_deleting_file(profile):
    """Null ImageField via UPDATE so storage file is kept for the new profile."""
    type(profile).objects.filter(pk=profile.pk).update(profile_image='')


def _unique_id_for(model, field_name, preferred, user_id):
    preferred = (preferred or '').strip()
    if preferred and not preferred.startswith('TEMP_'):
        if not model.objects.filter(**{field_name: preferred}).exists():
            return preferred
    candidate = f'TEMP_{user_id}'
    if not model.objects.filter(**{field_name: candidate}).exists():
        return candidate
    return f'TEMP_{user_id}_{uuid.uuid4().hex[:8]}'


# Fields shared by PatientProfile and StaffProfile (copied on role change).
SHARED_PROFILE_FIELDS = (
    'middle_name',
    'gender',
    'civil_status',
    'religion',
    'citizenship',
    'date_of_birth',
    'place_of_birth',
    'age',
    'address',
    'zip_code',
    'phone',
    'telephone_number',
    'emergency_contact',
    'emergency_phone',
    'department',
    'course',
    'year_level',
    'blood_type',
    'allergies',
    'medical_conditions',
    'position',
    'specialization',
    'license_number',
    'ptr_no',
)


def _shared_profile_values(source, target_model=None):
    """Copy retained profile fields from *source* onto kwargs for *target_model*."""
    nullable = {'date_of_birth', 'age', 'blood_type'}
    target_names = None
    if target_model is not None:
        target_names = {field.name for field in target_model._meta.fields}

    values = {}
    for field in SHARED_PROFILE_FIELDS:
        if not hasattr(source, field):
            continue
        if target_names is not None and field not in target_names:
            continue
        values[field] = getattr(source, field, None if field in nullable else '')
    return values


def swap_profile_for_role_change(user, old_role):
    """
    Move the user to the profile model for their new role, preserving shared data.
    Returns True when a profile type swap occurred.
    """
    if old_role == user.role:
        return False

    # Clear cached reverse relations so hasattr/get checks are fresh.
    user.__dict__.pop('patient_profile', None)
    user.__dict__.pop('staff_profile', None)
    user._state.fields_cache.pop('patient_profile', None)
    user._state.fields_cache.pop('staff_profile', None)

    if role_matches(old_role, ROLE_PATIENT) and not role_matches(user.role, ROLE_PATIENT):
        try:
            old = user.patient_profile
        except StudentProfile.DoesNotExist:
            old = None
        if old is None:
            if not StaffProfile.objects.filter(user=user).exists():
                StaffProfile.objects.create(
                    user=user,
                    staff_id=_unique_id_for(StaffProfile, 'staff_id', '', user.id),
                    phone='',
                    department='',
                )
            return True

        values = _shared_profile_values(old, StaffProfile)
        image_name = _profile_image_name(old)
        staff_id = _unique_id_for(StaffProfile, 'staff_id', old.patient_id, user.id)
        _clear_profile_image_without_deleting_file(old)
        old.delete()

        staff = StaffProfile.objects.create(
            user=user,
            staff_id=staff_id,
            **values,
        )
        if image_name:
            StaffProfile.objects.filter(pk=staff.pk).update(profile_image=image_name)
        return True

    if role_matches(old_role, 'staff', 'doctor', 'admin') and role_matches(user.role, ROLE_PATIENT):
        try:
            old = user.staff_profile
        except StaffProfile.DoesNotExist:
            old = None
        if old is None:
            if not StudentProfile.objects.filter(user=user).exists():
                StudentProfile.objects.create(
                    user=user,
                    patient_id=_unique_id_for(StudentProfile, 'patient_id', '', user.id),
                    phone='',
                    emergency_contact='',
                    emergency_phone='',
                )
            return True

        values = _shared_profile_values(old, StudentProfile)
        image_name = _profile_image_name(old)
        patient_id = _unique_id_for(StudentProfile, 'patient_id', old.staff_id, user.id)
        _clear_profile_image_without_deleting_file(old)
        old.delete()

        patient = StudentProfile.objects.create(
            user=user,
            patient_id=patient_id,
            **values,
        )
        if image_name:
            StudentProfile.objects.filter(pk=patient.pk).update(profile_image=image_name)
        return True

    return False
