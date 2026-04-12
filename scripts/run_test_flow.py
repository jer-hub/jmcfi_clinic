from django.contrib.auth import get_user_model
from django.utils import timezone

from core.models import StudentProfile, StaffProfile
from document_request.models import DocumentRequest
from document_request.models import MedicalCertificate

User = get_user_model()

# Create or get doctor
doc_email = 'test.doctor@example.com'
doctor, created = User.objects.get_or_create(email=doc_email, defaults={
    'first_name': 'Doc', 'last_name': 'Tester', 'role': 'doctor', 'is_staff': True, 'username': 'doc_test'
})
if created:
    doctor.set_password('testpass')
    doctor.save()

sp, _ = StaffProfile.objects.get_or_create(user=doctor, defaults={
    'staff_id': 'DOC001', 'department': 'Clinic', 'position': 'Doctor',
    'license_number': 'LIC-TEST', 'ptr_no': 'PTR-TEST'
})
# Ensure staff profile has license and ptr set
sp.license_number = sp.license_number or 'LIC-TEST'
sp.ptr_no = sp.ptr_no or 'PTR-TEST'
sp.department = sp.department or 'Clinic'
sp.position = sp.position or 'Doctor'
sp.save()

# Create or get student
stu_email = 'test.student@example.com'
student, created = User.objects.get_or_create(email=stu_email, defaults={
    'first_name': 'Stu', 'last_name': 'Dent', 'role': 'student', 'username': 'stu_test'
})
if created:
    student.set_password('testpass')
    student.save()

sst, _ = StudentProfile.objects.get_or_create(user=student, defaults={
    'student_id': 'STU001', 'age': 21, 'gender': 'male', 'address': '123 Test St'
})
# Ensure student profile fields are present
sst.student_id = sst.student_id or 'STU001'
sst.age = sst.age or 21
sst.gender = sst.gender or 'male'
sst.address = sst.address or '123 Test St'
sst.save()

# Create DocumentRequest and linked MedicalCertificate (simulate view behavior)
doc_request = DocumentRequest.objects.create(
    student=student, document_type='medical_certificate', purpose='Test flow', additional_info='None'
)

cert = MedicalCertificate.objects.create(
    user=student,
    status=MedicalCertificate.Status.PENDING,
    certificate_date=timezone.now().date(),
    patient_name=student.get_full_name(),
    consultation_date=timezone.now().date(),
    remarks_recommendations='None',
    age=sst.age,
    gender=sst.gender,
    address=sst.address,
)

doc_request.medical_certificate = cert
doc_request.save()

print('Created DocumentRequest id:', doc_request.id)
print('Created MedicalCertificate id:', cert.id)
print('Certificate initial patient_name, age, gender, address:')
print(cert.patient_name, cert.age, cert.gender, cert.address)

# Simulate doctor editing and signing the certificate
cert.physician_name = f"{doctor.first_name} {doctor.last_name}".strip()
cert.license_no = sp.license_number
cert.ptr_no = sp.ptr_no
cert.status = MedicalCertificate.Status.COMPLETED
cert.signed_by = doctor
cert.signed_at = timezone.now()
cert.save()

# Persist some fields back to student profile
changed = False
if cert.age and sst.age != cert.age:
    sst.age = cert.age
    changed = True
if cert.gender and sst.gender != cert.gender:
    sst.gender = cert.gender
    changed = True
if cert.address and sst.address != cert.address:
    sst.address = cert.address
    changed = True
if changed:
    sst.save()

print('After doctor review — certificate physician/license/ptr:')
print('Physician:', cert.physician_name)
print('License No:', cert.license_no)
print('PTR No:', cert.ptr_no)
print('Student profile now — age/gender/address:')
print('Age:', sst.age)
print('Gender:', sst.gender)
print('Address:', sst.address)
