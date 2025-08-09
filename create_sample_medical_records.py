#!/usr/bin/env python
"""
Script to create sample medical records for testing.
Run this script from the Django project root: python create_sample_medical_records.py
"""
import os
import sys
import django
from datetime import date, datetime, timedelta
from django.utils import timezone

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from core.models import User
from management.models import (
    Appointment, MedicalRecord, StudentProfile, StaffProfile, CertificateRequest
)

def create_sample_data():
    """Create sample medical records for testing"""
    
    # Create or get sample users
    try:
        # Create student if doesn't exist
        student_user, created = User.objects.get_or_create(
            email='student@example.com',
            defaults={
                'username': 'student_user',
                'first_name': 'John',
                'last_name': 'Doe',
                'role': 'student',
                'is_active': True,
            }
        )
        if created:
            student_user.set_password('password123')
            student_user.save()
            
            # Create student profile
            StudentProfile.objects.get_or_create(
                user=student_user,
                defaults={
                    'student_id': 'STU001',
                    'date_of_birth': date(1995, 5, 15),
                    'phone': '+1234567890',
                    'emergency_contact': 'Jane Doe',
                    'emergency_phone': '+1234567891',
                    'blood_type': 'A+',
                    'allergies': 'None',
                    'medical_conditions': 'None'
                }
            )
            print(f"Created student user: {student_user.email}")
        
        # Create staff/doctor if doesn't exist
        doctor_user, created = User.objects.get_or_create(
            email='doctor@example.com',
            defaults={
                'username': 'doctor_user',
                'first_name': 'Sarah',
                'last_name': 'Smith',
                'role': 'staff',
                'is_active': True,
            }
        )
        if created:
            doctor_user.set_password('password123')
            doctor_user.save()
            
            # Create staff profile
            StaffProfile.objects.get_or_create(
                user=doctor_user,
                defaults={
                    'staff_id': 'DOC001',
                    'department': 'General Medicine',
                    'specialization': 'Family Medicine',
                    'license_number': 'LIC123456',
                    'phone': '+1234567892'
                }
            )
            print(f"Created doctor user: {doctor_user.email}")
            
        # Create sample appointment
        appointment, created = Appointment.objects.get_or_create(
            student=student_user,
            doctor=doctor_user,
            date=timezone.now().date() - timedelta(days=1),  # Yesterday
            time=datetime.strptime('10:00', '%H:%M').time(),
            defaults={
                'appointment_type': 'consultation',
                'reason': 'Regular checkup and flu symptoms',
                'status': 'completed'
            }
        )
        if created:
            print(f"Created sample appointment: {appointment}")
        
        # Create sample medical record
        medical_record, created = MedicalRecord.objects.get_or_create(
            student=student_user,
            doctor=doctor_user,
            appointment=appointment,
            defaults={
                'diagnosis': 'Common cold with mild upper respiratory symptoms. Patient presents with nasal congestion, mild sore throat, and low-grade fever.',
                'treatment': 'Rest and increased fluid intake recommended. Symptomatic treatment with over-the-counter medications. Monitor temperature and return if symptoms worsen.',
                'prescription': 'Acetaminophen 500mg every 6 hours as needed for fever/pain\nSaline nasal spray 2-3 times daily\nThroat lozenges as needed',
                'vital_signs': {
                    'blood_pressure': '120/80',
                    'temperature': '99.2',
                    'heart_rate': '72',
                    'weight': '70.5'
                },
                'lab_results': 'Rapid strep test: Negative\nTemperature: 99.2°F',
                'follow_up_required': True,
                'follow_up_date': timezone.now().date() + timedelta(days=7)
            }
        )
        if created:
            print(f"Created sample medical record: {medical_record}")
            
        # Create another medical record from a few weeks ago
        old_appointment, created = Appointment.objects.get_or_create(
            student=student_user,
            doctor=doctor_user,
            date=timezone.now().date() - timedelta(days=21),
            time=datetime.strptime('14:30', '%H:%M').time(),
            defaults={
                'appointment_type': 'checkup',
                'reason': 'Annual health screening',
                'status': 'completed'
            }
        )
        
        old_record, created = MedicalRecord.objects.get_or_create(
            student=student_user,
            doctor=doctor_user,
            appointment=old_appointment,
            defaults={
                'diagnosis': 'Annual health screening completed. Overall good health with no significant concerns.',
                'treatment': 'Continue current lifestyle habits. Regular exercise and balanced diet recommended.',
                'prescription': 'Multivitamin supplement daily\nContinue current medications as prescribed',
                'vital_signs': {
                    'blood_pressure': '118/78',
                    'temperature': '98.6',
                    'heart_rate': '68',
                    'weight': '69.8'
                },
                'lab_results': 'Complete Blood Count: Normal\nLipid Panel: Within normal limits\nBlood glucose: 88 mg/dL',
                'follow_up_required': False
            }
        )
        if created:
            print(f"Created historical medical record: {old_record}")
            
        # Create a sample certificate request
        certificate_request, created = CertificateRequest.objects.get_or_create(
            student=student_user,
            certificate_type='fitness',
            defaults={
                'purpose': 'Employment requirements',
                'additional_info': 'Required for part-time job application',
                'status': 'ready',  # Make it ready for testing
                'processed_by': doctor_user
            }
        )
        if created:
            print(f"Created sample certificate request: {certificate_request}")
            
        # Create another certificate request (pending)
        certificate_request2, created = CertificateRequest.objects.get_or_create(
            student=student_user,
            certificate_type='absence',
            defaults={
                'purpose': 'School absence documentation',
                'additional_info': 'Missed classes due to flu',
                'status': 'pending'
            }
        )
        if created:
            print(f"Created sample certificate request 2: {certificate_request2}")
            
        print("\n✅ Sample medical records created successfully!")
        print("\nYou can now test the medical records functionality with:")
        print(f"Student login: {student_user.email} / password123")
        print(f"Doctor login: {doctor_user.email} / password123")
        print("\nNavigate to http://127.0.0.1:8000/ to test the system.")
        print("- Students can view and print their certificates from the Certificate Requests page")
        print("- Ready certificates can be printed, approved certificates can be viewed")
        
    except Exception as e:
        print(f"❌ Error creating sample data: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    create_sample_data()
