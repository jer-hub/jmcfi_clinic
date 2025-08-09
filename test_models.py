#!/usr/bin/env python
import os
import sys
import django

# Add the project directory to the Python path
sys.path.append('D:/jmcfi_clinic')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from core.models import User
from management.models import *
from django.utils import timezone
import datetime

def test_models():
    print("Testing Healthcare Management System Models...")
    
    try:
        # Create test users
        student = User.objects.create_user(
            username='test_student',
            email='student@test.com',
            password='testpass123',
            first_name='John',
            last_name='Doe',
            role='student'
        )
        print(f"✓ Created student: {student.get_full_name()}")
        
        staff = User.objects.create_user(
            username='test_staff',
            email='staff@test.com',
            password='testpass123',
            first_name='Dr. Jane',
            last_name='Smith',
            role='staff'
        )
        print(f"✓ Created staff: {staff.get_full_name()}")
        
        # Create student profile
        student_profile = StudentProfile.objects.create(
            user=student,
            student_id='STU001',
            date_of_birth=datetime.date(2000, 1, 1),
            phone='1234567890',
            emergency_contact='Jane Doe',
            emergency_phone='0987654321',
            blood_type='A+',
            allergies='None',
            medical_conditions='None'
        )
        print(f"✓ Created student profile: {student_profile.student_id}")
        
        # Create staff profile
        staff_profile = StaffProfile.objects.create(
            user=staff,
            staff_id='DOC001',
            department='General Medicine',
            specialization='Family Medicine',
            license_number='LIC123456',
            phone='1111111111'
        )
        print(f"✓ Created staff profile: {staff_profile.staff_id}")
        
        # Create appointment
        appointment = Appointment.objects.create(
            student=student,
            doctor=staff,
            appointment_type='consultation',
            date=timezone.now().date(),
            time=timezone.now().time(),
            reason='General checkup',
            status='pending'
        )
        print(f"✓ Created appointment: {appointment.id}")
        
        # Create medical record
        medical_record = MedicalRecord.objects.create(
            student=student,
            doctor=staff,
            appointment=appointment,
            diagnosis='Healthy',
            treatment='None required',
            prescription='None',
            vital_signs={'bp': '120/80', 'temp': '98.6'},
            lab_results='Normal',
            follow_up_required=False
        )
        print(f"✓ Created medical record: {medical_record.id}")
        
        # Create certificate request
        certificate_request = CertificateRequest.objects.create(
            student=student,
            certificate_type='fitness',
            purpose='Sports participation',
            additional_info='Required for basketball team',
            status='pending'
        )
        print(f"✓ Created certificate request: {certificate_request.id}")
        
        # Create health tip
        health_tip = HealthTip.objects.create(
            title='Stay Hydrated',
            content='Drink at least 8 glasses of water daily.',
            category='nutrition',
            created_by=staff,
            is_active=True
        )
        print(f"✓ Created health tip: {health_tip.title}")
        
        # Create notification
        notification = Notification.objects.create(
            user=student,
            title='Appointment Reminder',
            message='Your appointment is scheduled for tomorrow.',
            notification_type='appointment',
            is_read=False
        )
        print(f"✓ Created notification: {notification.title}")
        
        # Create feedback
        feedback = Feedback.objects.create(
            student=student,
            appointment=appointment,
            rating=5,
            comments='Excellent service!',
            suggestions='Keep up the good work',
            is_anonymous=False
        )
        print(f"✓ Created feedback: {feedback.rating}/5")
        
        print("\n✅ All models tested successfully!")
        
        # Test role methods
        print("\n📋 Testing role methods:")
        print(f"Student is_student(): {student.is_student()}")
        print(f"Staff is_staff: {staff.is_staff}")
        print(f"Student role: {student.role}")
        print(f"Staff role: {staff.role}")
        
        # Test model counts
        print(f"\n📊 Model counts:")
        print(f"Users: {User.objects.count()}")
        print(f"Student Profiles: {StudentProfile.objects.count()}")
        print(f"Staff Profiles: {StaffProfile.objects.count()}")
        print(f"Appointments: {Appointment.objects.count()}")
        print(f"Medical Records: {MedicalRecord.objects.count()}")
        print(f"Certificate Requests: {CertificateRequest.objects.count()}")
        print(f"Health Tips: {HealthTip.objects.count()}")
        print(f"Notifications: {Notification.objects.count()}")
        print(f"Feedback: {Feedback.objects.count()}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    test_models()
