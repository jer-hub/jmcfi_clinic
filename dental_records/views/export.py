"""Dental record JSON export view."""

from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from core.decorators import role_required
from dental_records.models import (
    DentalHealthQuestionnaire,
    DentalRecord,
    DentalSystemsReview,
    DentalVitalSigns,
)
from .helpers import _audit_dental


@login_required
@role_required('doctor')
def dental_record_export_json(request, record_id):
    """Export dental record as JSON for AI processing or backup"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    
    _audit_dental(request, dental_record, 'export', format='json')
    
    # Build comprehensive JSON structure
    data = {
        "demographics": {
            "lastName": dental_record.patient.last_name,
            "firstName": dental_record.patient.first_name,
            "middleName": dental_record.middle_name,
            "age": dental_record.age,
            "gender": dental_record.gender,
            "civilStatus": dental_record.civil_status,
            "address": dental_record.address,
            "dateOfBirth": dental_record.date_of_birth.isoformat() if dental_record.date_of_birth else None,
            "placeOfBirth": dental_record.place_of_birth,
            "email": dental_record.email,
            "contactNumber": dental_record.contact_number,
            "telephoneNumber": dental_record.telephone_number,
            "designation": dental_record.designation,
            "departmentCollegeOffice": dental_record.department_college_office,
            "emergencyContact": {
                "name": dental_record.guardian_name,
                "contactNumber": dental_record.guardian_contact
            },
            "dateOfExamination": dental_record.date_of_examination.isoformat() if dental_record.date_of_examination else None
        }
    }
    
    # Add health questionnaire
    try:
        hq = dental_record.health_questionnaire
        data["healthQuestionnaire"] = {
            "lastHospitalConfinement": {
                "date": hq.last_hospital_date.isoformat() if hq.last_hospital_date else None,
                "reason": hq.last_hospital_reason
            },
            "lastDoctorConsultation": {
                "date": hq.last_doctor_date.isoformat() if hq.last_doctor_date else None,
                "reason": hq.last_doctor_reason
            },
            "doctorCareSupervision": {
                "answer": hq.doctor_care_2years,
                "reason": hq.doctor_care_reason
            },
            "excessiveBleeding": {
                "answer": hq.excessive_bleeding,
                "when": hq.excessive_bleeding_when
            },
            "medicationsLast2Years": {
                "answer": hq.medications_2years,
                "for": hq.medications_for
            },
            "easilyExhausted": hq.easily_exhausted,
            "swollenAnkles": hq.swollen_ankles,
            "moreThan2Pillows": {
                "answer": hq.more_than_2_pillows,
                "why": hq.pillows_reason
            },
            "tumorCancerDiagnosis": {
                "answer": hq.tumor_cancer,
                "when": hq.tumor_cancer_when
            },
            "forWomen": {
                "pregnant": {
                    "answer": hq.is_pregnant,
                    "months": hq.pregnancy_months
                },
                "birthControlPills": {
                    "answer": hq.birth_control_pills,
                    "specify": hq.birth_control_specify
                },
                "anticipatePregnancy": hq.anticipate_pregnancy,
                "havingPeriod": hq.having_period
            }
        }
    except DentalHealthQuestionnaire.DoesNotExist:
        data["healthQuestionnaire"] = {}
    
    # Add systems review
    try:
        sr = dental_record.systems_review
        conditions = []
        for field in sr._meta.fields:
            if isinstance(field, models.BooleanField) and getattr(sr, field.name):
                conditions.append(field.name)
        data["systemsReview"] = conditions
        if sr.allergies:
            data["allergies"] = sr.allergies
        if sr.other_conditions:
            data["otherConditions"] = sr.other_conditions
    except DentalSystemsReview.DoesNotExist:
        data["systemsReview"] = []
    
    # Add vital signs
    try:
        vs = dental_record.vital_signs
        data["vitalSigns"] = {
            "bloodPressure": vs.blood_pressure,
            "pulseRate": vs.pulse_rate,
            "respiratoryRate": vs.respiratory_rate,
            "temperature": vs.temperature,
            "weight": vs.weight,
            "height": vs.height
        }
    except DentalVitalSigns.DoesNotExist:
        data["vitalSigns"] = {}
    
    data["consentSigned"] = dental_record.consent_signed
    data["signatureDate"] = dental_record.consent_date.isoformat() if dental_record.consent_date else None
    
    return JsonResponse(data, json_dumps_params={'indent': 2})
