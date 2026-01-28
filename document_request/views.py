from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta

from .models import DocumentRequest
from core.models import Notification

User = get_user_model()


@login_required
def document_requests(request):
    """View list of document/certificate requests."""
    if request.user.role == 'student':
        requests_qs = DocumentRequest.objects.filter(student=request.user)
    elif request.user.role in ['staff', 'admin']:
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
    
    context = {
        'requests': requests_page,
        'total_count': total_count,
        'pending_count': pending_count,
        'current_status': status,
        'current_type': document_type,
        'certificate_types': DocumentRequest.DOCUMENT_TYPES,
        'status_choices': DocumentRequest.STATUS_CHOICES,
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
        
        # Check for recent duplicate requests
        recent_request = DocumentRequest.objects.filter(
            student=request.user,
            document_type=document_type,
            created_at__gte=timezone.now() - timedelta(days=7),
            status__in=['pending', 'approved']
        ).first()
        
        if recent_request:
            messages.warning(
                request, 
                f'You already have a recent request for this certificate type '
                f'(submitted {recent_request.created_at.strftime("%B %d, %Y")}). '
                f'Please wait for it to be processed.'
            )
            return redirect('document_request:document_requests')
        
        try:
            # Create the document request
            doc_request = DocumentRequest.objects.create(
                student=request.user,
                document_type=document_type,
                purpose=purpose,
                additional_info=additional_info
            )
            
            # Create notification for staff/admin
            staff_users = User.objects.filter(role__in=['staff', 'admin'])
            notification_count = 0
            for staff in staff_users:
                Notification.objects.create(
                    user=staff,
                    title='New Certificate Request',
                    message=f'{request.user.get_full_name()} has requested a {dict(DocumentRequest.DOCUMENT_TYPES)[document_type]}',
                    notification_type='certificate'
                )
                notification_count += 1
            
            messages.success(request, f'Certificate request submitted successfully! Request ID: {doc_request.id}')
            messages.info(request, f'Notifications sent to {notification_count} staff members. You will be notified when your request is processed.')
            
            return redirect('document_request:document_requests')
            
        except Exception as e:
            messages.error(request, 'An error occurred while submitting your request. Please try again.')
            return render(request, 'document_request/request_document.html', {
                'certificate_types': DocumentRequest.DOCUMENT_TYPES,
            })
    
    context = {
        'certificate_types': DocumentRequest.DOCUMENT_TYPES,
    }
    
    return render(request, 'document_request/request_document.html', context)


@login_required
def process_document(request, request_id):
    """Process a document/certificate request (staff/admin only)."""
    if request.user.role not in ['staff', 'admin']:
        messages.error(request, 'Access denied')
        return redirect('core:dashboard')
    
    doc_request = get_object_or_404(DocumentRequest, id=request_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        rejection_reason = request.POST.get('rejection_reason', '')
        
        if action == 'approve':
            doc_request.status = 'approved'
            doc_request.processed_by = request.user
            message = 'Certificate request approved successfully!'
            
            # Create notification for student
            Notification.objects.create(
                user=doc_request.student,
                title='Certificate Request Approved',
                message=f'Your {dict(DocumentRequest.DOCUMENT_TYPES)[doc_request.document_type]} request has been approved and is being prepared.',
                notification_type='certificate'
            )
            
        elif action == 'reject':
            if not rejection_reason:
                messages.error(request, 'Please provide a reason for rejection.')
                return render(request, 'document_request/process_document.html', {'cert_request': doc_request})
                
            doc_request.status = 'rejected'
            doc_request.rejection_reason = rejection_reason
            doc_request.processed_by = request.user
            message = 'Certificate request rejected.'
            
            # Create notification for student
            Notification.objects.create(
                user=doc_request.student,
                title='Certificate Request Rejected',
                message=f'Your {dict(DocumentRequest.DOCUMENT_TYPES)[doc_request.document_type]} request has been rejected. Reason: {rejection_reason}',
                notification_type='certificate'
            )
            
        elif action == 'ready':
            doc_request.status = 'ready'
            doc_request.processed_by = request.user
            message = 'Certificate marked as ready for collection.'
            
            # Create notification for student
            Notification.objects.create(
                user=doc_request.student,
                title='Certificate Ready',
                message=f'Your {dict(DocumentRequest.DOCUMENT_TYPES)[doc_request.document_type]} is ready for collection at the clinic.',
                notification_type='certificate'
            )
        else:
            messages.error(request, 'Invalid action.')
            return render(request, 'document_request/process_document.html', {'cert_request': doc_request})
        
        doc_request.save()
        messages.success(request, message)
        return redirect('document_request:document_requests')
    
    return render(request, 'document_request/process_document.html', {'cert_request': doc_request})


@login_required
def view_document(request, request_id):
    """View a certificate in printable format."""
    doc_request = get_object_or_404(DocumentRequest, id=request_id)
    
    # Check permissions - students can only view their own certificates
    if request.user.role == 'student' and doc_request.student != request.user:
        messages.error(request, 'Access denied')
        return redirect('document_request:document_requests')
    
    # Only allow viewing of approved or ready certificates
    if doc_request.status not in ['approved', 'ready']:
        messages.error(request, 'Certificate is not ready for viewing')
        return redirect('document_request:document_requests')
    
    # Prepare certificate data
    context = {
        'cert_request': doc_request,
        'issue_date': timezone.now().date(),
        'certificate_number': f"JMCFI-{doc_request.id:06d}",
    }
    
    return render(request, 'document_request/view_document.html', context)


@login_required 
def print_document(request, request_id):
    """Print a certificate - returns a print-optimized view."""
    doc_request = get_object_or_404(DocumentRequest, id=request_id)
    
    # Check permissions
    if request.user.role == 'student' and doc_request.student != request.user:
        messages.error(request, 'Access denied')
        return redirect('document_request:document_requests')
    
    # Only allow printing of ready certificates
    if doc_request.status != 'ready':
        messages.error(request, 'Certificate is not ready for printing')
        return redirect('document_request:document_requests')
    
    # Prepare certificate data
    context = {
        'cert_request': doc_request,
        'issue_date': timezone.now().date(),
        'certificate_number': f"JMCFI-{doc_request.id:06d}",
    }
    
    return render(request, 'document_request/print_document.html', context)
