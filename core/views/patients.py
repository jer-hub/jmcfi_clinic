"""Patient search and guest registration views."""

import json

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from core.decorators import role_required
from core.roles import PATIENT_ROLE_VALUES
from core.utils import patient_search_q, patient_search_result_for_picker, student_display_name

User = get_user_model()


@login_required
@require_POST
@role_required('staff', 'doctor', 'admin')
def register_guest_patient(request):
    """Staff/doctor: create a clinic-managed guest patient for clinical workflows."""
    from core.doctor_access import ALL_MODULE_KEYS, has_clinical_module
    from core.guest_auth import create_guest_user

    content_type = request.content_type or ''
    if 'application/json' in content_type:
        try:
            data = json.loads(request.body.decode() or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
    else:
        data = request.POST

    module = (data.get('clinical_module') or '').strip()
    if module not in ALL_MODULE_KEYS:
        return JsonResponse({'error': 'Invalid clinical module'}, status=400)
    if not has_clinical_module(request.user, module):
        return JsonResponse({'error': 'Module not enabled for your account'}, status=403)

    first_name = (data.get('first_name') or '').strip()
    last_name = (data.get('last_name') or '').strip()
    if not first_name or not last_name:
        return JsonResponse({'error': 'First and last name are required'}, status=400)

    phone = (data.get('phone') or '').strip() or None
    contact_email = (data.get('email') or data.get('contact_email') or '').strip() or None
    gender = (data.get('gender') or '').strip() or None
    dob_raw = (data.get('date_of_birth') or '').strip()
    date_of_birth = None
    if dob_raw:
        try:
            from datetime import datetime
            date_of_birth = datetime.strptime(dob_raw, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'error': 'Invalid date of birth'}, status=400)

    user = create_guest_user(
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        gender=gender,
        date_of_birth=date_of_birth,
        contact_email=contact_email,
    )
    return JsonResponse(patient_search_result_for_picker(user), status=201)


@login_required
@role_required('staff', 'doctor', 'admin')
def search_patients(request):
    """
    AJAX endpoint to search for patients by name or email.
    Used in forms where staff/doctors need to select a patient.
    Guests are excluded — use Register guest patient for those accounts.
    """
    from core.guest_auth import exclude_guest_users

    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse([], safe=False)

    patients = exclude_guest_users(
        User.objects.filter(Q(role__in=PATIENT_ROLE_VALUES) & patient_search_q(query))
        .select_related('patient_profile')
        .distinct()
    )[:10]

    results = []
    for patient in patients:
        profile = getattr(patient, 'patient_profile', None)
        name = student_display_name(patient)
        patient_id = getattr(profile, 'patient_id', '') if profile else ''
        results.append({
            'id': patient.id,
            'name': name,
            'text': name,
            'email': patient.email,
            'patient_id': patient_id,
            'course': getattr(profile, 'course', '') if profile else '',
            'year_level': getattr(profile, 'year_level', '') if profile else '',
        })
    return JsonResponse(results, safe=False)
