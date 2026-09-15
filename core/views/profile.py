"""Profile views."""

import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from core.academic_catalog import (
    is_course_optional_for_department,
    patient_catalog_context,
    year_levels_by_college,
)
from core.forms import clean_strict_ph_number
from core.models import CollegeDepartment, CourseProgram, YearLevelOption
from core.profile_forms import patient_catalog_context_for_form, profile_form_class
from core.roles import ROLE_PATIENT, role_matches
from core.settings_service import get_profile_required_fields
from core.utils import (
    age_from_date_of_birth,
    get_missing_profile_fields,
    get_user_profile,
    normalize_person_name,
    person_display_name,
)
from dental_records.models import DentalRecord


@login_required
def profile_required(request):
    """View to show profile completion required page – access to all services is blocked."""
    missing = get_missing_profile_fields(request.user)
    required_fields = get_profile_required_fields(request.user.role)
    if role_matches(request.user.role, ROLE_PATIENT):
        from core.guest_auth import GUEST_INSTITUTIONAL_FIELDS, is_guest_user
        profile = get_user_profile(request.user)
        if is_guest_user(request.user):
            required_fields = [
                f for f in required_fields
                if f not in GUEST_INSTITUTIONAL_FIELDS
            ]
        elif profile and getattr(profile, 'is_employee', False):
            required_fields = [
                f for f in required_fields
                if f not in {'course', 'year_level'}
            ]

    required_count = len(required_fields) if required_fields else 0
    missing_count = len(missing)
    filled_count = max(required_count - missing_count, 0)
    completion_percentage = (
        int(round((filled_count / required_count) * 100))
        if required_count
        else 100
    )

    return render(request, 'core/profile_required.html', {
        'missing_fields': missing,
        'missing_count': missing_count,
        'required_count': required_count,
        'filled_count': filled_count,
        'completion_percentage': completion_percentage,
    })


@login_required
def profile_view(request):
    """Display user profile information"""
    profile = get_user_profile(request.user)
    missing_fields = get_missing_profile_fields(request.user)

    # Completion % uses the same required set as the gate (guests skip institutional).
    completion_percentage = 100
    if profile:
        required_fields = get_profile_required_fields(request.user.role)
        if role_matches(request.user.role, ROLE_PATIENT):
            from core.guest_auth import GUEST_INSTITUTIONAL_FIELDS, is_guest_user
            if is_guest_user(request.user):
                required_fields = [
                    f for f in required_fields
                    if f not in GUEST_INSTITUTIONAL_FIELDS
                ]
            elif getattr(profile, 'is_employee', False):
                required_fields = [
                    f for f in required_fields
                    if f not in {'course', 'year_level'}
                ]
        if required_fields:
            filled_count = len(required_fields) - len(missing_fields)
            completion_percentage = max(0, min(100, int((filled_count / len(required_fields)) * 100)))
    
    catalog = patient_catalog_context()
    year_level_options_by_college = year_levels_by_college()
    active_college = profile.department if profile and role_matches(request.user.role, ROLE_PATIENT) else ''
    year_level_options = year_level_options_by_college.get(active_college, [])

    dental_record = None
    try:
        dental_record = DentalRecord.objects.filter(patient=request.user).latest('created_at')
    except DentalRecord.DoesNotExist:
        pass

    context = {
        'user': request.user,
        'profile': profile,
        'dental_record': dental_record,
        'completion_percentage': completion_percentage,
        'missing_fields': missing_fields,
        'course_options': catalog['course_options'],
        'college_options': catalog['college_options'],
        'course_options_by_college_json': catalog['course_options_by_college_json'],
        'college_options_json': catalog['college_options_json'],
        'course_optional_by_college_json': catalog['course_optional_by_college_json'],
        'year_level_options': year_level_options,
        'year_level_options_by_college_json': catalog['year_level_options_by_college_json'],
    }
    
    return render(request, 'core/profile.html', context)


@login_required
def quick_edit_profile(request):
    """Quick edit a single profile field via AJAX/form submission"""
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    if request.method != 'POST':
        if is_ajax:
            return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)
        messages.error(request, 'Invalid request method.')
        return redirect('core:profile')
    
    profile = get_user_profile(request.user)
    if not profile:
        if is_ajax:
            return JsonResponse({'success': False, 'error': 'Profile not found. Please complete your profile first.'}, status=404)
        messages.error(request, 'Profile not found. Please complete your profile first.')
        return redirect('core:edit_profile')
    
    field_name = request.POST.get('field_name')
    field_value = request.POST.get('field_value', '').strip()
    selected_college = request.POST.get('selected_college', '').strip()

    if field_name == 'academic_bundle':
        if not role_matches(request.user.role, ROLE_PATIENT):
            if is_ajax:
                return JsonResponse({'success': False, 'error': 'Academic quick edit is only available for patients.'}, status=400)
            messages.error(request, 'Academic quick edit is only available for patients.')
            return redirect('core:profile')

        from core.guest_auth import is_guest_user
        if is_guest_user(request.user):
            if is_ajax:
                return JsonResponse({'success': False, 'error': 'Academic information is not used for guest patients.'}, status=400)
            messages.error(request, 'Academic information is not used for guest patients.')
            return redirect('core:profile')

        department = request.POST.get('department', '').strip()
        year_level = request.POST.get('year_level', '').strip()
        course = request.POST.get('course', '').strip()

        try:
            valid_colleges = set(
                CollegeDepartment.objects.filter(is_active=True)
                .values_list('name', flat=True)
            )
            if department not in valid_colleges:
                raise ValueError('Invalid College selection.')

            course_is_optional = is_course_optional_for_department(department)
            if not course and not course_is_optional:
                raise ValueError('Course/Program is required.')

            valid_courses = set(
                CourseProgram.objects.filter(
                    is_active=True,
                    college_department__name=department,
                ).values_list('name', flat=True)
            )
            if course and course not in valid_courses:
                raise ValueError('Invalid Course/Program for selected College.')

            valid_year_levels = set(
                YearLevelOption.objects.filter(
                    is_active=True,
                    college_department__name=department,
                ).values_list('name', flat=True)
            )
            if year_level not in valid_year_levels:
                raise ValueError('Invalid Year Level for selected College.')

            profile.department = department
            profile.year_level = year_level
            profile.course = course
            profile.save(update_fields=['department', 'year_level', 'course'])

            session_key = f'profile_complete_{request.user.id}_{request.user.role}'
            if session_key in request.session:
                del request.session[session_key]
            legacy_key = f'profile_complete_{request.user.id}'
            if legacy_key in request.session:
                del request.session[legacy_key]

            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'message': 'Academic information updated successfully.',
                    'field_name': 'academic_bundle',
                    'academic_payload': {
                        'department': department,
                        'year_level': year_level,
                        'course': course,
                    },
                })

            messages.success(request, 'Academic information updated successfully.')
            return redirect('core:profile')
        except ValueError as e:
            if is_ajax:
                return JsonResponse({'success': False, 'error': f'Error updating field: {str(e)}'}, status=400)
            messages.error(request, f'Error updating field: {str(e)}')
            return redirect('core:profile')
    
    # Define allowed fields for quick edit (security measure)
    allowed_fields = [
        'academic_bundle',
        'first_name', 'last_name',
        'phone', 'telephone_number', 'emergency_contact', 'emergency_phone',
        'address', 'allergies', 'medical_conditions', 'middle_name',
        'place_of_birth', 'religion', 'citizenship', 'course', 'year_level', 'department',
        'specialization'
    ]

    if request.user.role == 'doctor':
        doctor_blocked_fields = {'allergies', 'medical_conditions', 'blood_type'}
        allowed_fields = [f for f in allowed_fields if f not in doctor_blocked_fields]
        for doctor_field in ('staff_id', 'license_number', 'ptr_no'):
            if doctor_field not in allowed_fields:
                allowed_fields.append(doctor_field)
    elif request.user.role == 'admin':
        admin_blocked_fields = {
            'allergies',
            'medical_conditions',
            'blood_type',
            'department',
            'position',
            'specialization',
        }
        allowed_fields = [f for f in allowed_fields if f not in admin_blocked_fields]
    
    # Fields that need special handling
    date_fields = ['date_of_birth']
    integer_fields = ['age']
    select_fields = ['gender', 'civil_status', 'blood_type']

    if request.user.role == 'admin':
        select_fields = [f for f in select_fields if f != 'blood_type']
    
    all_allowed = allowed_fields + date_fields + select_fields
    
    if field_name not in all_allowed:
        if is_ajax:
            return JsonResponse({'success': False, 'error': 'This field cannot be edited via quick edit.'}, status=400)
        messages.error(request, 'This field cannot be edited via quick edit.')
        return redirect('core:profile')
    
    user_fields = {'first_name', 'last_name'}
    target_obj = request.user if field_name in user_fields else profile

    # Validate the field exists on target model
    if not hasattr(target_obj, field_name):
        if is_ajax:
            return JsonResponse({'success': False, 'error': 'Invalid field.'}, status=400)
        messages.error(request, 'Invalid field.')
        return redirect('core:profile')
    
    try:
        text_max_lengths = {
            'address': 500,
            'place_of_birth': 200,
            'religion': 100,
            'citizenship': 100,
            'course': 100,
            'year_level': 20,
            'department': 100,
            'position': 100,
            'specialization': 100,
        }

        if field_name == 'address':
            # Keep intentional newlines but normalize surrounding whitespace.
            field_value = '\n'.join(line.strip() for line in field_value.splitlines()).strip()
            if not field_value:
                raise ValueError('Address is required.')
            if len(field_value) < 5:
                raise ValueError('Address must be at least 5 characters.')

        if field_name in ['first_name', 'last_name']:
            field_value = normalize_person_name(field_value)
            if not field_value:
                raise ValueError(f'{field_name.replace("_", " ").title()} is required.')
            if len(field_value) > 150:
                raise ValueError(f'{field_name.replace("_", " ").title()} must be 150 characters or fewer.')
            if not re.fullmatch(r"[A-Za-z][A-Za-z .'-]*", field_value):
                raise ValueError(f'{field_name.replace("_", " ").title()} contains invalid characters.')

        if field_name == 'middle_name':
            field_value = normalize_person_name(field_value)
            if field_value and len(field_value) > 100:
                raise ValueError('Middle Name must be 100 characters or fewer.')
            if field_value and not re.fullmatch(r"[A-Za-z][A-Za-z .'-]*", field_value):
                raise ValueError('Middle Name contains invalid characters.')

        if field_name in ['allergies', 'medical_conditions']:
            list_parts = re.split(r'[\n,;]+', field_value)
            clean_parts = []
            for part in list_parts:
                item = part.strip()
                if not item:
                    continue
                if len(item) > 120:
                    raise ValueError('Each list item must be 120 characters or fewer.')
                if item not in clean_parts:
                    clean_parts.append(item)

            if len(clean_parts) > 30:
                raise ValueError('Maximum 30 items allowed.')

            # Store as newline-delimited list for stable parsing/display.
            field_value = '\n'.join(clean_parts)

        if role_matches(request.user.role, ROLE_PATIENT) and field_name in ['course', 'year_level', 'department']:
            selected_college_name = selected_college or profile.department
            course_is_optional = is_course_optional_for_department(selected_college_name)

            if not field_value and not (field_name == 'course' and course_is_optional):
                raise ValueError(f'{field_name.replace("_", " ").title()} is required.')

            if field_name == 'course':
                if not selected_college_name:
                    raise ValueError('Select College first before selecting Course/Program.')

                # Prevent bypass: selected college must match persisted student college.
                if profile.department and selected_college and selected_college != profile.department:
                    raise ValueError('Selected college does not match your saved College. Update College first.')

                valid_courses = set(
                    CourseProgram.objects.filter(
                        is_active=True,
                        college_department__name=selected_college_name,
                    ).values_list('name', flat=True)
                )
                if field_value and field_value not in valid_courses:
                    raise ValueError('Invalid Course/Program for selected College.')

            if field_name == 'year_level':
                selected_college_name = selected_college or profile.department
                if not selected_college_name:
                    raise ValueError('Select College first before selecting Year Level.')

                valid_year_levels = set(
                    YearLevelOption.objects.filter(
                        is_active=True,
                        college_department__name=selected_college_name,
                    ).values_list('name', flat=True)
                )
                if field_value not in valid_year_levels:
                    raise ValueError('Invalid Year Level for selected College.')

            if field_name == 'department':
                valid_colleges = set(
                    CollegeDepartment.objects.filter(is_active=True)
                    .values_list('name', flat=True)
                )
                if field_value not in valid_colleges:
                    raise ValueError('Invalid College selection.')

                # Keep student course consistent with selected college.
                if role_matches(request.user.role, ROLE_PATIENT) and profile.course:
                    valid_courses = set(
                        CourseProgram.objects.filter(
                            is_active=True,
                            college_department__name=field_value,
                        ).values_list('name', flat=True)
                    )
                    if profile.course not in valid_courses:
                        profile.course = ''
                        profile.save(update_fields=['course'])

                if role_matches(request.user.role, ROLE_PATIENT) and profile.year_level:
                    valid_year_levels = set(
                        YearLevelOption.objects.filter(
                            is_active=True,
                            college_department__name=field_value,
                        ).values_list('name', flat=True)
                    )
                    if profile.year_level not in valid_year_levels:
                        profile.year_level = ''
                        profile.save(update_fields=['year_level'])

        if field_name in ['phone', 'telephone_number', 'emergency_phone']:
            phone_required = field_name == 'phone' or (
                field_name == 'emergency_phone' and role_matches(request.user.role, ROLE_PATIENT)
            )
            field_value = clean_strict_ph_number(field_value, required=phone_required)

        if field_name in ['gender', 'civil_status', 'blood_type']:
            valid_choices = {
                'gender': {'male', 'female', 'other', ''},
                'civil_status': {'single', 'married', 'widowed', 'separated', ''},
                'blood_type': {'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-', ''},
            }
            if field_value not in valid_choices[field_name]:
                raise ValueError(f'Invalid value for {field_name.replace("_", " ").title()}.')

        if field_name in text_max_lengths and len(field_value) > text_max_lengths[field_name]:
            raise ValueError(
                f'{field_name.replace("_", " ").title()} must be '
                f'{text_max_lengths[field_name]} characters or fewer.'
            )

        # Handle date fields
        if field_name in date_fields:
            if field_value:
                from datetime import datetime
                field_value = datetime.strptime(field_value, '%Y-%m-%d').date()
                if field_value > timezone.now().date():
                    raise ValueError('Date of Birth cannot be in the future.')
            else:
                field_value = None
        elif field_name in integer_fields:
            if field_value:
                field_value = int(field_value)
                if field_value < 0 or field_value > 150:
                    raise ValueError('Age must be between 0 and 150.')
            else:
                field_value = None
        
        # Set the value
        setattr(target_obj, field_name, field_value)
        computed_age = None
        if field_name == 'date_of_birth':
            computed_age = age_from_date_of_birth(field_value)
            target_obj.age = computed_age
        target_obj.save()

        raw_value = getattr(target_obj, field_name, '')
        if raw_value is None:
            raw_value = ''

        display_value = raw_value
        if field_name == 'gender':
            display_value = profile.get_gender_display() if raw_value else 'Not specified'
        elif field_name == 'civil_status':
            display_value = profile.get_civil_status_display() if raw_value else 'Not specified'
        elif field_name == 'blood_type':
            display_value = raw_value or '--'
        elif field_name == 'date_of_birth':
            display_value = raw_value.strftime('%B %d, %Y') if raw_value else 'Not specified'
            raw_value = raw_value.strftime('%Y-%m-%d') if raw_value else ''
        elif field_name == 'age':
            display_value = f'{raw_value} years old' if raw_value else 'Not specified'
        
        # Clear profile completion cache
        session_key = f'profile_complete_{request.user.id}_{request.user.role}'
        if session_key in request.session:
            del request.session[session_key]
        legacy_key = f'profile_complete_{request.user.id}'
        if legacy_key in request.session:
            del request.session[legacy_key]
        
        success_message = f'Successfully updated your {field_name.replace("_", " ").title()}.'
        if is_ajax:
            payload = {
                'success': True,
                'message': success_message,
                'field_name': field_name,
                'raw_value': raw_value,
                'display_value': display_value,
                'full_name': person_display_name(request.user, profile),
            }
            if field_name == 'date_of_birth':
                payload['age'] = computed_age if computed_age is not None else ''
                payload['age_display'] = (
                    f'{computed_age} years old' if computed_age is not None else 'Not specified'
                )
            return JsonResponse(payload)

        messages.success(request, success_message)
    except (ValueError, ValidationError) as e:
        error_text = str(e)
        if error_text.startswith("['") and error_text.endswith("']"):
            error_text = error_text[2:-2]
        if is_ajax:
            return JsonResponse({'success': False, 'error': f'Error updating field: {error_text}'}, status=400)
        messages.error(request, f'Error updating field: {error_text}')
    except Exception as e:
        if is_ajax:
            return JsonResponse({'success': False, 'error': f'Error updating field: {str(e)}'}, status=400)
        messages.error(request, f'Error updating field: {str(e)}')
    
    return redirect('core:profile')


@login_required
def edit_profile(request):
    """Edit user profile information"""
    profile = get_user_profile(request.user)
    is_first_time = profile is None
    
    try:
        form_class = profile_form_class(request.user)
    except ValueError:
        messages.error(request, 'Profile editing not available for your role.')
        return redirect('core:dashboard')
    
    # Check for dental record to auto-fill data
    dental_record = None
    try:
        dental_record = DentalRecord.objects.filter(patient=request.user).latest('created_at')
    except DentalRecord.DoesNotExist:
        pass
    
    if request.method == 'POST':
        # Handle auto-fill request
        if 'autofill_from_dental' in request.POST and dental_record:
            # Create initial data from dental record
            initial_data = {}
            
            if dental_record.middle_name:
                initial_data['middle_name'] = dental_record.middle_name
            if dental_record.gender:
                initial_data['gender'] = dental_record.gender
            if dental_record.civil_status:
                initial_data['civil_status'] = dental_record.civil_status
            if dental_record.date_of_birth:
                initial_data['date_of_birth'] = dental_record.date_of_birth
            if dental_record.place_of_birth:
                initial_data['place_of_birth'] = dental_record.place_of_birth
            if dental_record.age:
                initial_data['age'] = dental_record.age
            if dental_record.address:
                initial_data['address'] = dental_record.address
            if dental_record.contact_number:
                initial_data['phone'] = dental_record.contact_number
            if dental_record.telephone_number:
                initial_data['telephone_number'] = dental_record.telephone_number
            if dental_record.guardian_name:
                initial_data['emergency_contact'] = dental_record.guardian_name
            if dental_record.guardian_contact:
                initial_data['emergency_phone'] = dental_record.guardian_contact
            if dental_record.department_college_office:
                if role_matches(request.user.role, ROLE_PATIENT):
                    # Try to parse as course
                    initial_data['course'] = dental_record.department_college_office
                else:
                    initial_data['department'] = dental_record.department_college_office
            
            # Merge with existing profile data if available
            if profile:
                if request.user.role in ['staff', 'doctor', 'admin']:
                    form = form_class(initial=initial_data, instance=profile, user=request.user, editor=request.user)
                else:
                    form = form_class(initial=initial_data, instance=profile)
                # Update form with autofilled values
                for key, value in initial_data.items():
                    if key in form.fields:
                        form.initial[key] = value
            else:
                if request.user.role in ['staff', 'doctor', 'admin']:
                    form = form_class(initial=initial_data, user=request.user, editor=request.user)
                else:
                    form = form_class(initial=initial_data)
            
            messages.success(request, 'Profile auto-filled from your dental record. Please review and save.')
            
        else:
            # Normal form submission
            first_name = normalize_person_name(request.POST.get('first_name') or '')
            last_name = normalize_person_name(request.POST.get('last_name') or '')
            names_valid = True
            if not first_name or not last_name:
                messages.error(request, 'First Name and Last Name are required.')
                names_valid = False
                if request.user.role in ['staff', 'doctor', 'admin']:
                    form = form_class(request.POST, request.FILES, instance=profile, user=request.user, editor=request.user)
                else:
                    form = form_class(request.POST, request.FILES, instance=profile)
            elif request.user.role in ['staff', 'doctor', 'admin']:
                form = form_class(request.POST, request.FILES, instance=profile, user=request.user, editor=request.user)
            else:
                form = form_class(request.POST, request.FILES, instance=profile)
            if names_valid and form.is_valid():
                request.user.first_name = first_name
                request.user.last_name = last_name
                request.user.save(update_fields=['first_name', 'last_name'])

                profile = form.save(commit=False)
                if not profile.user_id:
                    profile.user = request.user
                profile.save()
                
                # Clear profile completion cache
                session_key = f'profile_complete_{request.user.id}_{request.user.role}'
                if session_key in request.session:
                    del request.session[session_key]
                legacy_key = f'profile_complete_{request.user.id}'
                if legacy_key in request.session:
                    del request.session[legacy_key]
                
                if is_first_time:
                    messages.success(request, 'Welcome! Your profile has been created successfully!')
                    # Clear the welcome shown flag
                    request.session.pop('profile_welcome_shown', None)
                else:
                    messages.success(request, 'Profile updated successfully!')
                
                # Redirect to profile page after successful save
                return redirect('core:profile')
            else:
                if is_first_time:
                    messages.error(request, 'Please complete all required fields to set up your profile.')
                else:
                    messages.error(request, 'Please correct the errors below.')
    else:
        if request.user.role in ['staff', 'doctor', 'admin']:
            form = form_class(instance=profile, user=request.user, editor=request.user)
        else:
            form = form_class(instance=profile)
        
        # Only show welcome message for first-time users, and only once per session
        if is_first_time and not request.session.get('profile_welcome_shown'):
            messages.info(request, 
                f'Welcome to JMCFI Clinic! Please complete your profile to get started.')
            request.session['profile_welcome_shown'] = True
    
    catalog_context = {}
    include_academic_catalog = False
    if role_matches(request.user.role, ROLE_PATIENT):
        from core.guest_auth import is_guest_user
        include_academic_catalog = not is_guest_user(request.user)
        if include_academic_catalog:
            catalog_context = patient_catalog_context_for_form(form, request.user)

    context = {
        'form': form,
        'profile': profile,
        'user': request.user,
        'subject_user': request.user,
        'is_first_time': is_first_time,
        'dental_record': dental_record,
        'include_academic_catalog': include_academic_catalog,
        **catalog_context,
    }
    
    return render(request, 'core/edit_profile.html', context)
