from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.conf import settings
from datetime import datetime
from django.db import IntegrityError
import pdfkit
from pathlib import Path

from .models import DocumentRequest, MedicalCertificate, DoctorSignature
from core.models import Notification
from .forms import DoctorSignatureForm, MedicalCertificateForm

User = get_user_model()


ALLOWED_DOCUMENT_TYPES = [('medical_certificate', 'Medical Certificate')]


def _resolve_wkhtmltopdf_path():
    """Resolve wkhtmltopdf executable path for pdfkit."""
    configured = getattr(settings, 'WKHTMLTOPDF_CMD', '')
    candidates = [
        configured,
        r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
        r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def _build_request_form_context(user, extra_context=None):
    context = {
        'certificate_types': ALLOWED_DOCUMENT_TYPES,
        'is_doctor_flow': user.role in ['doctor', 'admin'],
        'students': User.objects.filter(role='student').order_by('last_name', 'first_name') if user.role in ['doctor', 'admin'] else None,
    }
    if hasattr(user, 'student_profile') and user.student_profile:
        context['student_profile'] = user.student_profile
    if extra_context:
        context.update(extra_context)
    return context


@login_required
def document_requests(request):
    """View list of document/certificate requests."""
    signature = None
    signature_form = None

    if request.user.role == 'doctor':
        signature = DoctorSignature.objects.filter(doctor=request.user).first()
        signature_form = DoctorSignatureForm(instance=signature)

        if request.method == 'POST' and request.POST.get('signature_action') == 'save_signature':
            signature_form = DoctorSignatureForm(request.POST, request.FILES, instance=signature)
            if signature_form.is_valid():
                signature = signature_form.save(commit=False)
                signature.doctor = request.user
                signature.updated_by = request.user
                signature.save()
                messages.success(request, 'Your signature has been updated successfully.')
                return redirect('document_request:document_requests')

    if request.user.role == 'student':
        requests_qs = DocumentRequest.objects.filter(student=request.user)
    elif request.user.role in ['admin', 'doctor']:
        requests_qs = DocumentRequest.objects.all()
    else:
        requests_qs = DocumentRequest.objects.none()
    
    # Apply filters
    status = request.GET.get('status')
    document_type = request.GET.get('type')
    
    if status:
        requests_qs = requests_qs.filter(status=status)
    
    if document_type:
        requests_qs = requests_qs.filter(document_type=document_type)

    # Status totals for the currently filtered result set
    pending_count = requests_qs.filter(status='pending').count()
    completed_count = requests_qs.filter(status='completed').count()
    rejected_count = requests_qs.filter(status='rejected').count()
    
    requests_qs = requests_qs.order_by('-created_at')
    
    paginator = Paginator(requests_qs, 10)
    page = request.GET.get('page')
    requests_page = paginator.get_page(page)
    
    # Total count for the currently filtered result set
    total_count = requests_qs.count()
    
    # Build status choices based on role
    if request.user.role == 'student':
        # Simplified labels for students
        status_choices = [
            ('pending', 'Processing'),
            ('completed', 'Ready'),
            ('rejected', 'Rejected'),
        ]
    else:
        status_choices = DocumentRequest.STATUS_CHOICES
    
    context = {
        'requests': requests_page,
        'total_count': total_count,
        'pending_count': pending_count,
        'status_totals': {
            'pending': pending_count,
            'completed': completed_count,
            'rejected': rejected_count,
        },
        'current_status': status,
        'current_type': document_type,
        'certificate_types': ALLOWED_DOCUMENT_TYPES,
        'status_choices': status_choices,
        'signature': signature,
        'signature_form': signature_form,
    }
    
    return render(request, 'document_request/document_requests.html', context)


@login_required
def request_document(request):
    """Submit a new document/certificate request."""
    if request.user.role not in ['student', 'doctor', 'admin']:
        messages.error(request, 'Only students, doctors, and admins can request documents')
        return redirect('core:dashboard')

    base_context = _build_request_form_context(request.user)

    if request.method == 'POST':
        document_type = request.POST.get('certificate_type') or request.POST.get('document_type')
        purpose = request.POST.get('purpose')
        additional_info = request.POST.get('additional_info', '')
        student = request.user

        if request.user.role in ['doctor', 'admin']:
            student_id = request.POST.get('student_id')
            if not student_id:
                messages.error(request, 'Student is required.')
                return render(request, 'document_request/request_document.html', base_context)
            student = get_object_or_404(User, pk=student_id, role='student')
        
        # Validation with enhanced messages
        validation_errors = []
        
        if not document_type:
            validation_errors.append('Certificate type is required')
        if not purpose:
            validation_errors.append('Purpose is required')
        
        if validation_errors:
            for error in validation_errors:
                messages.error(request, error)
            return render(request, 'document_request/request_document.html', base_context)
        
        # Only medical certificate requests are accepted for now.
        if document_type != 'medical_certificate':
            messages.error(request, 'Only Medical Certificate requests are accepted at this time.')
            return render(request, 'document_request/request_document.html', base_context)

        # Check for existing pending requests (prevent duplicate pending requests)
        pending_request = DocumentRequest.objects.filter(
            student=student,
            document_type=document_type,
            status='pending'
        ).first()
        
        if pending_request:
            messages.warning(
                request,
                'You already have a pending document request. '
                'Please wait for it to be processed.'
            )
            return redirect('document_request:document_requests')
        
        try:
            # Create the document request
            doc_request = DocumentRequest.objects.create(
                student=student,
                created_by=request.user,
                request_origin='doctor' if request.user.role in ['doctor', 'admin'] else 'student',
                document_type=document_type,
                purpose=purpose,
                additional_info=additional_info,
                status='pending'  # Will be updated when certificate is created
            )

            if doc_request.requires_medical_certificate:
                # Auto-create a new MedicalCertificate for this student
                # Allow submitted profile overrides (age/gender/address) -- fall back to stored profile
                posted_age = request.POST.get('age')
                posted_gender = request.POST.get('gender')
                posted_address = request.POST.get('address')

                profile_data = {}
                if posted_age or posted_gender or posted_address:
                    try:
                        age_val = int(posted_age) if posted_age else None
                    except Exception:
                        age_val = None
                    profile_data = {
                        'age': age_val,
                        'gender': posted_gender or '',
                        'address': posted_address or '',
                    }
                else:
                    if hasattr(student, 'student_profile') and student.student_profile:
                        profile = student.student_profile
                        profile_data = {
                            'age': profile.age,
                            'gender': profile.gender,
                            'address': profile.address,
                        }

                cert = MedicalCertificate.objects.create(
                    user=student,
                    status=MedicalCertificate.Status.PENDING,
                    certificate_date=timezone.now().date(),
                    patient_name=student.get_full_name(),
                    consultation_date=timezone.now().date(),
                    diagnosis='',
                    physician_name=request.user.get_full_name() or request.user.email if request.user.role in ['doctor', 'admin'] else '',
                    remarks_recommendations=additional_info or '',
                    **profile_data  # Auto-fill age, gender, address from student profile or submitted values
                )

                # Link the certificate to the request
                doc_request.medical_certificate = cert
                doc_request.save(update_fields=['medical_certificate', 'updated_at'])
            
            # Create notification for authorized processors
            staff_users = User.objects.filter(role__in=['admin', 'doctor'])
            for staff in staff_users:
                Notification.objects.create(
                    user=staff,
                    title='New Certificate Request',
                    message=f'{request.user.get_full_name()} has requested a {dict(DocumentRequest.DOCUMENT_TYPES).get(document_type, "certificate")} and a certificate has been auto-created for review.',
                    notification_type='certificate',
                    transaction_type='certificate_requested',
                    related_id=doc_request.id
                )
            
            messages.success(request, f'Your {doc_request.get_document_type_display().lower()} request has been submitted successfully.')
            
            # Redirect to document requests page to show status
            return redirect('document_request:document_requests')
        except IntegrityError:
            messages.warning(request, 'You already have a pending request of this type.')
            return redirect('document_request:document_requests')
        except Exception as e:
            messages.error(request, 'An error occurred while submitting your request. Please try again.')
            return render(request, 'document_request/request_document.html', base_context)

    return render(request, 'document_request/request_document.html', base_context)


@login_required
def edit_medical_certificate(request, cert_id):
    """Edit a medical certificate linked to a document request."""
    certificate = get_object_or_404(MedicalCertificate, id=cert_id)
    
    # Check permissions - only doctors and admins can edit
    if request.user.role not in ['doctor', 'admin']:
        messages.error(request, 'Access denied')
        return redirect('document_request:document_requests')
    
    # Get the linked document request (if any)
    linked_doc_request = DocumentRequest.objects.filter(medical_certificate=certificate).first()
    
    # Check for missing signature
    signature = DoctorSignature.objects.filter(doctor=request.user).first()
    missing_signature_warning = not signature
    
    if request.method == 'POST':
        form = MedicalCertificateForm(request.POST, instance=certificate)
        
        if form.is_valid():
            form.save()
            messages.success(request, 'Certificate details saved successfully.')
            
            # Redirect back to the document request process page if linked
            if linked_doc_request:
                return redirect('document_request:process_document', request_id=linked_doc_request.id)
            else:
                return redirect('document_request:document_requests')
    else:
        # Prefill physician and student details when certificate fields empty
        initial = {}
        try:
            student = certificate.user
            if hasattr(student, 'student_profile') and student.student_profile:
                profile = student.student_profile
                if not certificate.age and profile.age:
                    initial['age'] = profile.age
                if (not certificate.gender or certificate.gender == '') and profile.gender:
                    initial['gender'] = profile.gender
                if (not certificate.address or certificate.address == '') and profile.address:
                    initial['address'] = profile.address
                if (not certificate.patient_name or certificate.patient_name == ''):
                    initial['patient_name'] = student.get_full_name()
        except Exception:
            initial = {}

        # Prefill physician details from current user when available
        try:
            user = request.user
            if user and user.role in ['doctor', 'admin']:
                if not certificate.physician_name and not initial.get('physician_name'):
                    initial['physician_name'] = user.get_full_name() or user.email or ''

                # License number: try staff_profile then common attributes
                lic = ''
                if hasattr(user, 'staff_profile') and getattr(user, 'staff_profile'):
                    lic = getattr(user.staff_profile, 'license_number', '') or ''
                lic = lic or getattr(user, 'license_number', '') or getattr(user, 'license_no', '') or ''
                if lic and not certificate.license_no and not initial.get('license_no'):
                    initial['license_no'] = lic

                # PTR no: try common attributes on user or staff_profile
                ptr = getattr(user, 'ptr_no', '') or getattr(user, 'ptrno', '') or ''
                if not ptr and hasattr(user, 'staff_profile') and getattr(user, 'staff_profile'):
                    ptr = getattr(user.staff_profile, 'ptr_no', '') or getattr(user.staff_profile, 'ptrno', '') or ''
                if ptr and not certificate.ptr_no and not initial.get('ptr_no'):
                    initial['ptr_no'] = ptr
        except Exception:
            pass

        form = MedicalCertificateForm(instance=certificate, initial=initial)
    
    context = {
        'certificate': certificate,
        'form': form,
        'linked_doc_request': linked_doc_request,
        'missing_signature_warning': missing_signature_warning,
    }
    
    return render(request, 'document_request/edit_medical_certificate.html', context)


@login_required
def process_document(request, request_id):
    """Process a document/certificate request - accessible to all roles for viewing."""
    doc_request = get_object_or_404(DocumentRequest, id=request_id)
    
    # Check permissions - students can only view their own certificates
    if request.user.role == 'student' and doc_request.student != request.user:
        messages.error(request, 'Access denied')
        return redirect('document_request:document_requests')
    elif request.user.role not in ['student', 'doctor', 'admin']:
        messages.error(request, 'Access denied')
        return redirect('document_request:document_requests')
    
    # Only doctor/admin can process, students can only view their own
    can_process = request.user.role in ['admin', 'doctor']

    if request.method == 'POST' and can_process:
        action = request.POST.get('action')
        rejection_reason = request.POST.get('rejection_reason', '')

        if action == 'review':
            # Mark complete after cert review
            if doc_request.requires_medical_certificate:
                if not doc_request.medical_certificate:
                    messages.error(request, 'No medical certificate found for this request.')
                    return render(request, 'document_request/process_document.html', {
                        'cert_request': doc_request, 
                        'can_process': can_process
                    })
                # Check if diagnosis/recommendations filled
                if not doc_request.medical_certificate.diagnosis or not doc_request.medical_certificate.remarks_recommendations:
                    messages.warning(request, 'Please fill in diagnosis and remarks before completing.')
                    return render(request, 'document_request/process_document.html', {
                        'cert_request': doc_request, 
                        'can_process': can_process
                    })

            doc_request.status = 'completed'
            doc_request.processed_by = request.user
            doc_request.save(update_fields=['status', 'processed_by', 'updated_at'])

            # Mark cert as completed
            if doc_request.medical_certificate:
                doc_request.medical_certificate.status = MedicalCertificate.Status.COMPLETED
                doc_request.medical_certificate.save()

            Notification.objects.create(
                user=doc_request.student,
                title='Record Request Completed',
                message=f'Your {doc_request.get_document_type_display()} request is now ready.',
                notification_type='certificate',
                transaction_type='certificate_ready',
                related_id=doc_request.id
            )
            messages.success(request, 'Record request marked as completed.')
            return redirect('document_request:document_requests')

        elif action == 'reject':
            if not rejection_reason:
                messages.error(request, 'Please provide a reason for rejection.')
                return render(request, 'document_request/process_document.html', {
                    'cert_request': doc_request, 
                    'can_process': can_process
                })

            doc_request.status = 'rejected'
            doc_request.rejection_reason = rejection_reason
            doc_request.processed_by = request.user

            # Also reject the linked certificate if any
            if doc_request.requires_medical_certificate and doc_request.medical_certificate:
                doc_request.medical_certificate.status = MedicalCertificate.Status.REJECTED
                doc_request.medical_certificate.save()

            # Create notification for student
            Notification.objects.create(
                user=doc_request.student,
                title='Certificate Request Rejected',
                message=f'Your {dict(DocumentRequest.DOCUMENT_TYPES).get(doc_request.document_type, "certificate")} request has been rejected. Reason: {rejection_reason}',
                notification_type='certificate',
                transaction_type='certificate_rejected',
                related_id=doc_request.id
            )

            doc_request.save()
            messages.success(request, 'Certificate request rejected.')
            return redirect('document_request:document_requests')
        else:
            messages.error(request, 'Invalid action.')
            return render(request, 'document_request/process_document.html', {
                'cert_request': doc_request, 
                'can_process': can_process
            })

    return render(request, 'document_request/process_document.html', {
        'cert_request': doc_request, 
        'can_process': can_process
    })


@login_required
def view_document(request, request_id):
    """View a certificate – redirects to the process document request page for all roles."""
    doc_request = get_object_or_404(DocumentRequest, id=request_id)
    
    # Check permissions - students can only view their own certificates
    if request.user.role == 'student' and doc_request.student != request.user:
        messages.error(request, 'Access denied')
        return redirect('document_request:document_requests')
    elif request.user.role not in ['student', 'doctor', 'admin']:
        messages.error(request, 'Access denied')
        return redirect('document_request:document_requests')
    
    # Redirect to the process document request page for all roles regardless of status
    return redirect('document_request:process_document', request_id=request_id)


@login_required
def preview_medical_certificate(request, cert_id):
    """Preview medical certificate on dedicated page."""
    certificate = get_object_or_404(MedicalCertificate, id=cert_id)
    
    # Check permissions - students can only view their own, doctors/admins can view all
    if request.user.role == 'student' and certificate.user != request.user:
        messages.error(request, 'Access denied')
        return redirect('document_request:document_requests')
    elif request.user.role not in ['student', 'doctor', 'admin']:
        messages.error(request, 'Access denied')
        return redirect('document_request:document_requests')
    
    # Get linked document request (if any)
    linked_doc_request = DocumentRequest.objects.filter(medical_certificate=certificate).first()
    
    # Get physician signature (do not rely on requesting user, which may be student)
    physician_signature = None
    if certificate.signed_by:
        physician_signature = DoctorSignature.objects.filter(doctor=certificate.signed_by).first()
    if not physician_signature and certificate.reviewed_by:
        physician_signature = DoctorSignature.objects.filter(doctor=certificate.reviewed_by).first()
    if not physician_signature:
        physician_signature = DoctorSignature.objects.filter(is_active=True).first()
    
    # Split multi-line text for template rendering
    diagnosis_lines = [line.strip() for line in (certificate.diagnosis or '').split('\n') if line.strip()][:5]
    remarks_lines = [line.strip() for line in (certificate.remarks_recommendations or '').split('\n') if line.strip()][:7]
    while len(diagnosis_lines) < 5:
        diagnosis_lines.append('')
    while len(remarks_lines) < 7:
        remarks_lines.append('')
    
    context = {
        'medical_certificate': certificate,
        'certificate': certificate,
        'linked_doc_request': linked_doc_request,
        'issue_date': certificate.certificate_date,
        'physician_signature': physician_signature,
        'diagnosis_lines': diagnosis_lines or [''],
        'remarks_lines': remarks_lines or [''],
    }
    
    return render(request, 'document_request/preview_medical_certificate.html', context)


@login_required
def download_medical_certificate_pdf(request, cert_id):
    """Download medical certificate as PDF."""
    certificate = get_object_or_404(MedicalCertificate, id=cert_id)
    
    # Check permissions
    if request.user.role == 'student' and certificate.user != request.user:
        messages.error(request, 'Access denied')
        return redirect('document_request:document_requests')
    elif request.user.role not in ['student', 'doctor', 'admin']:
        messages.error(request, 'Access denied')
        return redirect('document_request:document_requests')
    
    # Get physician signature (do not rely on requesting user, which may be student)
    physician_signature = None
    if certificate.signed_by:
        physician_signature = DoctorSignature.objects.filter(doctor=certificate.signed_by).first()
    if not physician_signature and certificate.reviewed_by:
        physician_signature = DoctorSignature.objects.filter(doctor=certificate.reviewed_by).first()
    if not physician_signature:
        physician_signature = DoctorSignature.objects.filter(is_active=True).first()
    
    # Split multi-line text for template rendering
    diagnosis_lines = [line.strip() for line in (certificate.diagnosis or '').split('\n') if line.strip()]
    remarks_lines = [line.strip() for line in (certificate.remarks_recommendations or '').split('\n') if line.strip()]
    
    # Prefer collected staticfiles font, then STATIC_ROOT, then source static directory.
    font_candidates = [
        Path(settings.BASE_DIR) / 'staticfiles' / 'fonts' / 'old-english-text-mt.ttf',
    ]
    static_root = getattr(settings, 'STATIC_ROOT', None)
    if static_root:
        font_candidates.append(Path(static_root) / 'fonts' / 'old-english-text-mt.ttf')
    font_candidates.append(Path(settings.BASE_DIR) / 'static' / 'fonts' / 'old-english-text-mt.ttf')

    font_path = next((candidate for candidate in font_candidates if candidate.exists()), None)
    old_english_font_uri = font_path.resolve().as_uri() if font_path else ''

    physician_signature_uri = ''
    if physician_signature and getattr(physician_signature, 'signature_image', None):
        try:
            sig_path = Path(physician_signature.signature_image.path)
            if sig_path.exists():
                physician_signature_uri = sig_path.resolve().as_uri()
        except Exception:
            physician_signature_uri = ''
    elif certificate.signature_snapshot:
        try:
            snap_path = Path(certificate.signature_snapshot.path)
            if snap_path.exists():
                physician_signature_uri = snap_path.resolve().as_uri()
        except Exception:
            physician_signature_uri = ''
    
    context = {
        'certificate': certificate,
        'physician_signature': physician_signature,
        'diagnosis_lines': diagnosis_lines,
        'remarks_lines': remarks_lines,
        'is_pdf': True,  # Flag to hide screen controls in template
        'old_english_font_uri': old_english_font_uri,
        'physician_signature_uri': physician_signature_uri,
    }
    html_string = render_to_string('document_request/certificate_pdf.html', context)

    wkhtmltopdf_path = _resolve_wkhtmltopdf_path()
    if not wkhtmltopdf_path:
        messages.error(request, 'wkhtmltopdf not found. Install it or set WKHTMLTOPDF_CMD in settings.')
        return redirect('document_request:preview_medical_certificate', cert_id=cert_id)

    options = {
        'page-size': 'Letter',
        'margin-top': '0.75in',
        'margin-right': '0.75in',
        'margin-bottom': '0.75in',
        'margin-left': '0.75in',
        'encoding': 'UTF-8',
        'enable-local-file-access': None,
        'quiet': None,
    }
    config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
    pdf_bytes = pdfkit.from_string(html_string, False, options=options, configuration=config)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="certificate_{certificate.id}.pdf"'
    return response
