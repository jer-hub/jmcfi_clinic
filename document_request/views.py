from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta

from .models import DocumentRequest
from core.models import Notification
from health_forms_services.models import MedicalCertificate

User = get_user_model()


@login_required
def document_requests(request):
    """View list of document/certificate requests."""
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
    
    requests_qs = requests_qs.order_by('-created_at')
    
    paginator = Paginator(requests_qs, 10)
    page = request.GET.get('page')
    requests_page = paginator.get_page(page)
    
    # Get counts for filtering
    if request.user.role == 'student':
        total_count = DocumentRequest.objects.filter(student=request.user).count()
        pending_count = DocumentRequest.objects.filter(student=request.user, status='pending').count()
    else:
        total_count = DocumentRequest.objects.count()
        pending_count = DocumentRequest.objects.filter(status='pending').count()
    
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
        'current_status': status,
        'current_type': document_type,
        'certificate_types': DocumentRequest.DOCUMENT_TYPES,
        'status_choices': status_choices,
    }
    
    return render(request, 'document_request/document_requests.html', context)


@login_required
def request_document(request):
    """Submit a new document/certificate request."""
    if request.user.role != 'student':
        messages.error(request, 'Only students can request certificates')
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        document_type = request.POST.get('certificate_type') or request.POST.get('document_type')
        purpose = request.POST.get('purpose')
        additional_info = request.POST.get('additional_info', '')
        
        # Validation with enhanced messages
        validation_errors = []
        
        if not document_type:
            validation_errors.append('Certificate type is required')
        if not purpose:
            validation_errors.append('Purpose is required')
        
        if validation_errors:
            for error in validation_errors:
                messages.error(request, error)
            return render(request, 'document_request/request_document.html', {
                'certificate_types': DocumentRequest.DOCUMENT_TYPES,
            })
        
        # Check if document type is valid
        valid_types = [choice[0] for choice in DocumentRequest.DOCUMENT_TYPES]
        if document_type not in valid_types:
            messages.error(request, 'Invalid certificate type selected.')
            return render(request, 'document_request/request_document.html', {
                'certificate_types': DocumentRequest.DOCUMENT_TYPES,
            })
        
        # Check for existing pending requests (prevent duplicate pending requests)
        pending_request = DocumentRequest.objects.filter(
            student=request.user,
            document_type=document_type,
            status='pending'
        ).first()
        
        if pending_request:
            messages.warning(
                request, 
                'You already have a pending certificate request. '
                'Please wait for it to be processed.'            )
            return redirect('document_request:document_requests')
        
        try:
            # Create the document request
            doc_request = DocumentRequest.objects.create(
                student=request.user,
                document_type=document_type,
                purpose=purpose,
                additional_info=additional_info,
                status='pending'  # Will be updated when certificate is created
            )
            
            # Auto-create a new MedicalCertificate for this student
            student = request.user

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
                remarks_recommendations=additional_info or '',
                **profile_data  # Auto-fill age, gender, address from student profile or submitted values
            )
            
            # Link the certificate to the request
            doc_request.medical_certificate = cert
            doc_request.save()
            
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
            
            messages.success(request, 'Your certificate request has been submitted successfully. You will be notified once it is ready for review.')
            
            # Redirect to document requests page to show status
            return redirect('document_request:document_requests')
            
        except Exception as e:
            messages.error(request, 'An error occurred while submitting your request. Please try again.')
            return render(request, 'document_request/request_document.html', {
                'certificate_types': DocumentRequest.DOCUMENT_TYPES,
            })
    
    context = {
        'certificate_types': DocumentRequest.DOCUMENT_TYPES,
    }

    # Include student profile data for pre-filling the form when available
    if hasattr(request.user, 'student_profile') and request.user.student_profile:
        context['student_profile'] = request.user.student_profile
    
    return render(request, 'document_request/request_document.html', context)


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
            # Redirect to edit the medical certificate (already created)
            if doc_request.medical_certificate:
                messages.info(request, 'Please review and complete the medical certificate details.')
                return redirect('health_forms_services:edit_medical_certificate', pk=doc_request.medical_certificate.pk)
            else:
                messages.error(request, 'No medical certificate found for this request.')
                return redirect('document_request:document_requests')

        elif action == 'reject':
            if not rejection_reason:
                messages.error(request, 'Please provide a reason for rejection.')
                return render(request, 'document_request/process_document.html', {'cert_request': doc_request, 'can_process': can_process})

            doc_request.status = 'rejected'
            doc_request.rejection_reason = rejection_reason
            doc_request.processed_by = request.user

            # Also reject the linked certificate if any
            if doc_request.medical_certificate:
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
            return render(request, 'document_request/process_document.html', {'cert_request': doc_request, 'can_process': can_process})

    return render(request, 'document_request/process_document.html', {'cert_request': doc_request, 'can_process': can_process})


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
def print_document(request, request_id):
    """Print a certificate – redirects to the health_forms_services print template."""
    doc_request = get_object_or_404(DocumentRequest, id=request_id)

    if request.user.role not in ['doctor', 'admin']:
        messages.error(request, 'Access denied. Printing certificates is restricted to authorized clinicians.')
        return redirect('document_request:document_requests')
    
    # Check permissions
    if request.user.role == 'student' and doc_request.student != request.user:
        messages.error(request, 'Access denied')
        return redirect('document_request:document_requests')
    elif request.user.role not in ['student', 'doctor', 'admin']:
        messages.error(request, 'Access denied')
        return redirect('document_request:document_requests')
    
    # Check status and provide appropriate messaging
    if doc_request.status == 'rejected':
        messages.error(request, 'This certificate request has been rejected. Please check the rejection reason and submit a new request if needed.')
        return redirect('document_request:document_requests')
    elif doc_request.status != 'completed':
        messages.info(request, 'Your certificate is being prepared. Please check back later.')
        return redirect('document_request:document_requests')
    
    # Redirect to the official medical certificate print template
    if doc_request.medical_certificate:
        return redirect('health_forms_services:export_medical_certificate_docx', pk=doc_request.medical_certificate.pk)
    
    # No linked certificate
    messages.info(request, 'Your certificate is being prepared. Please check back later.')
    return redirect('document_request:document_requests')
