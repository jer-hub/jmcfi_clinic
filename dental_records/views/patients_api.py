"""Patient search and profile API views for dental forms."""

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from core.decorators import role_required

User = get_user_model()


@login_required
@role_required('doctor')
def search_patients(request):
    """Search for authenticated patients by name, email, or ID for autocomplete.

    Guests are excluded — use Register guest patient for those accounts.
    """
    from core.guest_auth import exclude_guest_users
    from core.roles import PATIENT_ROLE_VALUES

    query = request.GET.get('q', '').strip()

    if len(query) < 2:
        return JsonResponse({'results': []})

    patients = exclude_guest_users(
        User.objects.filter(role__in=PATIENT_ROLE_VALUES).filter(
            models.Q(first_name__icontains=query)
            | models.Q(last_name__icontains=query)
            | models.Q(email__icontains=query)
            | models.Q(patient_profile__patient_id__icontains=query)
        )
    )[:20]
    
    results = []
    for patient in patients:
        # Get profile information if available
        profile_info = ""
        try:
            if hasattr(patient, 'studentprofile'):
                profile = patient.studentprofile
                profile_info = f"Student - {profile.course or 'N/A'}"
            elif hasattr(patient, 'staffprofile'):
                profile = patient.staffprofile
                profile_info = f"Staff - {profile.department or 'N/A'}"
        except:
            profile_info = patient.get_role_display() if hasattr(patient, 'get_role_display') else ""
        
        results.append({
            'id': patient.id,
            'text': f"{patient.last_name}, {patient.first_name}",
            'email': patient.email,
            'role': profile_info,
            'display': f"{patient.last_name}, {patient.first_name} - {patient.email} ({profile_info})"
        })
    
    return JsonResponse({'results': results})


@login_required
@role_required('doctor')
def get_patient_profile(request, patient_id):
    """Get full patient profile data for auto-filling dental forms"""
    patient = get_object_or_404(User, pk=patient_id)
    
    from datetime import date
    from core.guest_auth import is_guest_user, resolve_patient_contact_email

    data = {
        'first_name': patient.first_name,
        'last_name': patient.last_name,
        'email': patient.email,
        'student_id': '',
        'middle_name': '',
        'gender': '',
        'civil_status': '',
        'date_of_birth': '',
        'place_of_birth': '',
        'age': '',
        'address': '',
        'contact_number': '',
        'telephone_number': '',
        'designation': '',
        'department_college_office': '',
        'course': '',
        'year_level': '',
        'guardian_name': '',
        'guardian_contact': '',
        'is_guest': is_guest_user(patient),
        'contact_email': resolve_patient_contact_email(patient) or '',
    }
    
    # Get profile data based on user role
    try:
        if hasattr(patient, 'patient_profile'):
            profile = patient.patient_profile
            is_employee = bool(getattr(profile, 'is_employee', False))
            data.update({
                'student_id': profile.patient_id or '',
                'middle_name': profile.middle_name or '',
                'gender': profile.gender or '',
                'civil_status': profile.civil_status or '',
                'date_of_birth': profile.date_of_birth.isoformat() if profile.date_of_birth else '',
                'place_of_birth': profile.place_of_birth or '',
                'age': profile.age or '',
                'address': profile.address or '',
                'contact_number': profile.phone or '',
                'telephone_number': profile.telephone_number or '',
                'designation': '' if data['is_guest'] else ('employee' if is_employee else 'student'),
                'department_college_office': (
                    ''
                    if data['is_guest']
                    else (profile.department or '')
                ),
                'course': '' if (data['is_guest'] or is_employee) else (profile.course or ''),
                'year_level': '' if (data['is_guest'] or is_employee) else (profile.year_level or ''),
                'guardian_name': profile.emergency_contact or '',
                'guardian_contact': profile.emergency_phone or '',
                'email': resolve_patient_contact_email(patient) or patient.email,
                'contact_email': resolve_patient_contact_email(patient) or '',
            })
            
            # Calculate age from date of birth if not set
            if profile.date_of_birth and not data['age']:
                today = date.today()
                dob = profile.date_of_birth
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                data['age'] = age
                
        elif hasattr(patient, 'staff_profile'):
            profile = patient.staff_profile
            data.update({
                'student_id': profile.staff_id or '',  # Use staff_id for the student_id field
                'middle_name': profile.middle_name or '',
                'gender': profile.gender or '',
                'civil_status': profile.civil_status or '',
                'date_of_birth': profile.date_of_birth.isoformat() if profile.date_of_birth else '',
                'place_of_birth': profile.place_of_birth or '',
                'age': profile.age or '',
                'address': profile.address or '',
                'contact_number': profile.phone or '',
                'telephone_number': profile.telephone_number or '',
                'designation': 'employee',
                'department_college_office': profile.department or '',
                'guardian_name': profile.emergency_contact or '',
                'guardian_contact': profile.emergency_phone or '',
            })
            
            # Calculate age from date of birth if not set
            if profile.date_of_birth and not data['age']:
                today = date.today()
                dob = profile.date_of_birth
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                data['age'] = age
    except Exception as e:
        # Profile doesn't exist or error occurred
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching profile for patient {patient_id}: {str(e)}")
    
    return JsonResponse(data)
