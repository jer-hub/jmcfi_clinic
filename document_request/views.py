from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date

from core.decorators import role_required
from core.htmx_utils import is_htmx_request
from core.roles import PATIENT_ROLE_VALUES, is_patient_role

from .forms import ClinicianSignatureForm, MedicalCertificateForm, ProcessDocumentForm
from .models import DocumentRequest, MedicalCertificate
from .services import (
    ALLOWED_DOCUMENT_TYPES,
    LIST_PAGE_SIZE,
    CertificateIncompleteError,
    DocumentRequestServiceError,
    InvalidTransitionError,
    MissingCertificateError,
    PdfGenerationError,
    RejectionReasonRequiredError,
    SignatureRequiredError,
    apply_list_filters,
    approve_request,
    build_certificate_form_initial,
    create_document_request,
    get_certificate_signature_display,
    get_clinician_signature,
    get_document_requests_queryset,
    get_or_create_certificate_pdf_bytes,
    get_status_totals,
    reject_request,
    save_certificate_draft,
    user_can_initiate_on_behalf,
    user_can_process_documents,
)
from .services.policies import assert_can_download_pdf, assert_certificate_accessible

User = get_user_model()

_DOCUMENT_REQUEST_ACCESS_ROLES = ('student', 'doctor', 'staff', 'admin')
_DOCUMENT_REQUEST_LIST_ROLES = ('student', 'doctor', 'staff')
_CLINICIAN_SIGNATURE_ROLES = ('doctor', 'staff', 'admin')
_DOCUMENT_REQUEST_STATUS_KEYS = ('pending_review', 'completed', 'rejected')


def _document_request_stat_filter_url(get_params, status_key: str) -> str:
    q = get_params.copy()
    current = (q.get('status') or '').strip()
    if current == status_key:
        q.pop('status', None)
    else:
        q['status'] = status_key
    q.pop('page', None)
    base = reverse('document_request:document_requests')
    encoded = q.urlencode()
    return f'{base}?{encoded}' if encoded else base


def _document_request_stat_filter_urls(get_params) -> dict[str, str]:
    return {key: _document_request_stat_filter_url(get_params, key) for key in _DOCUMENT_REQUEST_STATUS_KEYS}


def _document_request_list_querystring(get_params) -> str:
    q = get_params.copy()
    q.pop('page', None)
    encoded = q.urlencode()
    return f'&{encoded}' if encoded else ''


def _service_error_message(exc: DocumentRequestServiceError) -> str:
    return exc.message or 'Unable to process this request.'


def _build_request_form_context(user, extra_context=None):
    context = {
        'certificate_types': ALLOWED_DOCUMENT_TYPES,
        'is_doctor_flow': user_can_initiate_on_behalf(user) and not is_patient_role(user.role),
        'patients': (
            User.objects.filter(role__in=PATIENT_ROLE_VALUES)
            .select_related('patient_profile')
            .order_by('last_name', 'first_name')
            if user_can_initiate_on_behalf(user) and not is_patient_role(user.role)
            else None
        ),
    }
    if hasattr(user, 'patient_profile') and user.patient_profile:
        context['patient_profile'] = user.patient_profile
    if extra_context:
        context.update(extra_context)
    return context


_REQUEST_DOCUMENT_ERROR_FIELD_ORDER = ('patient_id', 'document_type', 'purpose', '__all__')


def _request_document_form_message_list(messages_by_field: dict) -> list[str]:
    items = []
    for key in _REQUEST_DOCUMENT_ERROR_FIELD_ORDER:
        for message in messages_by_field.get(key) or []:
            items.append(message)
    return items


def _request_document_page_context(
    user,
    post=None,
    field_errors=None,
    field_warnings=None,
    extra_context=None,
):
    post = post if post is not None else {}
    ctx = _build_request_form_context(user, extra_context)
    field_errors = field_errors or {}
    field_warnings = field_warnings or {}
    ctx['field_errors'] = field_errors
    ctx['field_warnings'] = field_warnings
    ctx['form_error_list'] = _request_document_form_message_list(field_errors)
    ctx['form_warning_list'] = _request_document_form_message_list(field_warnings)
    non_field = field_errors.get('__all__') or []
    ctx['form_non_field_error'] = non_field[0] if non_field else ''
    ctx['form_data'] = {
        'document_type': post.get('document_type') or post.get('certificate_type') or 'medical_certificate',
        'purpose': post.get('purpose', ''),
        'additional_info': post.get('additional_info', ''),
        'patient_id': post.get('patient_id', ''),
    }
    if user_can_initiate_on_behalf(user) and not is_patient_role(user.role) and post.get('patient_id'):
        try:
            patient = User.objects.select_related('patient_profile').get(
                pk=post['patient_id'],
                role__in=PATIENT_ROLE_VALUES,
            )
            label = patient.get_full_name() or patient.email
            pid = ''
            if hasattr(patient, 'patient_profile') and patient.patient_profile:
                pid = patient.patient_profile.patient_id or ''
            ctx['selected_patient'] = {
                'id': patient.id,
                'label': label,
                'email': patient.email,
                'pid': pid,
            }
        except User.DoesNotExist:
            pass
    return ctx


def _render_request_document(
    request,
    post=None,
    field_errors=None,
    field_warnings=None,
    extra_context=None,
):
    context = _request_document_page_context(
        request.user,
        post=post,
        field_errors=field_errors,
        field_warnings=field_warnings,
        extra_context=extra_context,
    )
    return render(request, 'document_request/request_document.html', context)


def _ensure_student_document_access(user, doc_request: DocumentRequest) -> None:
    if is_patient_role(user.role) and doc_request.patient_id != user.id:
        raise PermissionDenied


def _ensure_certificate_access(user, certificate: MedicalCertificate) -> None:
    if is_patient_role(user.role) and certificate.user_id != user.id:
        raise PermissionDenied


def _redirect_if_certificate_locked(request, linked_doc_request: DocumentRequest | None):
    if not linked_doc_request:
        return None
    try:
        assert_certificate_accessible(linked_doc_request)
    except InvalidTransitionError as exc:
        messages.error(request, exc.message)
        return redirect(
            'document_request:document_request_detail',
            request_id=linked_doc_request.id,
        )
    return None


@login_required
@role_required(*_CLINICIAN_SIGNATURE_ROLES)
def clinician_signature(request):
    """Upload and manage the clinician signature used when completing certificates."""
    signature = get_clinician_signature(request.user)
    signature_form = ClinicianSignatureForm(instance=signature)

    if request.method == 'POST':
        signature_form = ClinicianSignatureForm(request.POST, request.FILES, instance=signature)
        if signature_form.is_valid():
            signature = signature_form.save(commit=False)
            signature.doctor = request.user
            signature.updated_by = request.user
            signature.save()
            messages.success(request, 'Your signature has been updated successfully.')
            return redirect('document_request:clinician_signature')

    return render(
        request,
        'document_request/clinician_signature.html',
        {
            'signature': signature,
            'signature_form': signature_form,
        },
    )


@login_required
@role_required(*_DOCUMENT_REQUEST_LIST_ROLES)
def document_requests(request):
    get_params = request.GET
    scoped_qs = get_document_requests_queryset(request.user)

    status = get_params.get('status')
    document_type = get_params.get('type')
    search = get_params.get('search')
    date_from = parse_date(get_params.get('date_from')) if get_params.get('date_from') else None
    date_to = parse_date(get_params.get('date_to')) if get_params.get('date_to') else None

    filtered_qs = apply_list_filters(
        scoped_qs,
        document_type=document_type,
        date_from=date_from,
        date_to=date_to,
    )
    status_totals = get_status_totals(filtered_qs)

    requests_qs = apply_list_filters(
        filtered_qs,
        status=status,
        search=search,
    )

    paginator = Paginator(requests_qs, LIST_PAGE_SIZE)
    requests_page = paginator.get_page(get_params.get('page'))
    total_count = requests_qs.count()
    list_status = (get_params.get('status') or '').strip()
    stat_filter_urls = _document_request_stat_filter_urls(get_params)

    context = {
        'requests': requests_page,
        'total_count': total_count,
        'status_totals': status_totals,
        'current_status': status,
        'current_type': document_type,
        'current_search': search or '',
        'filter_date_from': get_params.get('date_from', ''),
        'filter_date_to': get_params.get('date_to', ''),
        'certificate_types': ALLOWED_DOCUMENT_TYPES,
        'doc_filter_urls': stat_filter_urls,
        'doc_stat_active': {key: list_status == key for key in _DOCUMENT_REQUEST_STATUS_KEYS},
        'doc_list_querystring': _document_request_list_querystring(get_params),
    }

    if is_htmx_request(request):
        return render(request, 'document_request/_document_requests_filter_oob.html', context)
    return render(request, 'document_request/document_requests.html', context)


@login_required
@role_required(*_DOCUMENT_REQUEST_ACCESS_ROLES)
def request_document(request):
    if request.method == 'POST':
        post = request.POST
        document_type = post.get('certificate_type') or post.get('document_type')
        purpose = (post.get('purpose') or '').strip()
        additional_info = post.get('additional_info', '')
        student = request.user
        field_errors = {}

        if user_can_initiate_on_behalf(request.user) and not is_patient_role(request.user.role):
            patient_id = (post.get('patient_id') or '').strip()
            if not patient_id:
                field_errors['patient_id'] = ['Please select a patient from the search results.']
            else:
                try:
                    student = User.objects.get(pk=patient_id, role__in=PATIENT_ROLE_VALUES)
                except User.DoesNotExist:
                    field_errors['patient_id'] = [
                        'Please select a valid patient from the search results.',
                    ]

        if not document_type:
            field_errors['document_type'] = ['Certificate type is required.']
        if not purpose:
            field_errors['purpose'] = ['Purpose is required.']

        if field_errors:
            return _render_request_document(request, post=post, field_errors=field_errors)

        if document_type != 'medical_certificate':
            return _render_request_document(
                request,
                post=post,
                field_errors={
                    'document_type': ['Only Medical Certificate requests are accepted at this time.'],
                },
            )

        if DocumentRequest.objects.filter(
            patient=student,
            document_type=document_type,
            status=DocumentRequest.Status.PENDING_REVIEW,
        ).exists():
            student_label = student.get_full_name() or student.email
            if is_patient_role(request.user.role):
                pending_msg = (
                    'You already have a pending medical certificate request. '
                    'Please wait for it to be processed before submitting another.'
                )
            else:
                pending_msg = (
                    f'{student_label} already has a pending medical certificate request. '
                    'Complete or reject the existing request before creating a new one.'
                )
            return _render_request_document(
                request,
                post=post,
                field_warnings={'__all__': [pending_msg]},
            )

        try:
            create_document_request(
                actor=request.user,
                student=student,
                document_type=document_type,
                purpose=purpose,
                additional_info=additional_info,
                post=post,
            )
            if is_patient_role(request.user.role):
                success_msg = 'Your medical certificate request has been submitted successfully.'
            else:
                student_label = student.get_full_name() or student.email
                success_msg = f'Medical certificate request created for {student_label}.'
            messages.success(request, success_msg)
            return redirect('document_request:document_requests')
        except IntegrityError:
            return _render_request_document(
                request,
                post=post,
                field_warnings={
                    '__all__': [
                        'A pending request of this type already exists. '
                        'Check the requests list or try again shortly.',
                    ],
                },
            )
        except Exception:
            return _render_request_document(
                request,
                post=post,
                field_errors={
                    '__all__': ['An error occurred while submitting your request. Please try again.'],
                },
            )

    return _render_request_document(request)


@login_required
@role_required('doctor', 'staff', 'admin')
def edit_medical_certificate(request, cert_id):
    certificate = get_object_or_404(MedicalCertificate, id=cert_id)
    linked_doc_request = DocumentRequest.objects.filter(medical_certificate=certificate).first()
    locked_redirect = _redirect_if_certificate_locked(request, linked_doc_request)
    if locked_redirect:
        return locked_redirect
    signature = get_clinician_signature(request.user)
    missing_signature_warning = request.user.role in ('doctor', 'staff', 'admin') and not signature

    if request.method == 'POST':
        form = MedicalCertificateForm(request.POST, instance=certificate)
        if form.is_valid():
            save_certificate_draft(
                certificate=certificate,
                actor=request.user,
                form_cleaned_data=form.cleaned_data,
            )
            messages.success(request, 'Certificate details saved successfully.')
            if linked_doc_request:
                return redirect('document_request:document_request_detail', request_id=linked_doc_request.id)
            return redirect('document_request:document_requests')
    else:
        initial = build_certificate_form_initial(certificate, request.user)
        form = MedicalCertificateForm(instance=certificate, initial=initial)

    return render(
        request,
        'document_request/edit_medical_certificate.html',
        {
            'certificate': certificate,
            'form': form,
            'linked_doc_request': linked_doc_request,
            'missing_signature_warning': missing_signature_warning,
        },
    )


@login_required
@role_required(*_DOCUMENT_REQUEST_ACCESS_ROLES)
def document_request_detail(request, request_id):
    """Unified hub for viewing and processing a document request."""
    doc_request = get_object_or_404(
        get_document_requests_queryset(request.user).filter(pk=request_id)
    )
    try:
        _ensure_student_document_access(request.user, doc_request)
    except PermissionDenied:
        messages.error(request, 'Access denied')
        return redirect('document_request:document_requests')

    can_process = user_can_process_documents(request.user)
    processor_signature = get_clinician_signature(request.user)
    missing_signature = (
        request.user.role in ('doctor', 'staff', 'admin') and not processor_signature
    )

    if request.method == 'POST' and can_process:
        form = ProcessDocumentForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Invalid action.')
            return _document_request_detail_response(
                request, doc_request, can_process, missing_signature,
            )

        action = form.cleaned_data['action']
        try:
            if action == 'review':
                approve_request(doc_request, request.user)
                messages.success(request, 'Request approved — certificate is completed.')
                return redirect('document_request:document_requests')
            if action == 'reject':
                reject_request(
                    doc_request,
                    request.user,
                    form.cleaned_data.get('rejection_reason', ''),
                )
                messages.success(request, 'Certificate request rejected.')
                return redirect('document_request:document_requests')
        except DocumentRequestServiceError as exc:
            level = messages.warning if isinstance(exc, CertificateIncompleteError) else messages.error
            level(request, _service_error_message(exc))

    return _document_request_detail_response(request, doc_request, can_process, missing_signature)


def _document_request_detail_response(request, doc_request, can_process, missing_signature):
    is_student = is_patient_role(request.user.role)
    if is_student:
        page_title = 'My Document Request'
        page_subtitle = 'Track your certificate request status'
    elif doc_request.is_pending_review:
        page_title = 'Process Document Request'
        page_subtitle = 'Review and process the document request'
    else:
        page_title = 'Document Request'
        page_subtitle = 'Request details and certificate'

    return render(
        request,
        'document_request/document_request_detail.html',
        {
            'cert_request': doc_request,
            'can_process': can_process,
            'missing_signature': missing_signature,
            'page_title': page_title,
            'page_subtitle': page_subtitle,
        },
    )


@login_required
@role_required(*_DOCUMENT_REQUEST_ACCESS_ROLES)
def process_document(request, request_id):
    return redirect('document_request:document_request_detail', request_id=request_id)


@login_required
@role_required(*_DOCUMENT_REQUEST_ACCESS_ROLES)
def view_document(request, request_id):
    return redirect('document_request:document_request_detail', request_id=request_id)


@login_required
@role_required(*_DOCUMENT_REQUEST_ACCESS_ROLES)
def preview_medical_certificate(request, cert_id):
    certificate = get_object_or_404(MedicalCertificate, id=cert_id)
    try:
        _ensure_certificate_access(request.user, certificate)
    except PermissionDenied:
        messages.error(request, 'Access denied')
        return redirect('document_request:document_requests')

    linked_doc_request = DocumentRequest.objects.filter(medical_certificate=certificate).first()
    locked_redirect = _redirect_if_certificate_locked(request, linked_doc_request)
    if locked_redirect:
        return locked_redirect
    physician_signature = get_certificate_signature_display(certificate)

    diagnosis_lines = [line.strip() for line in (certificate.diagnosis or '').split('\n') if line.strip()][:5]
    remarks_lines = [
        line.strip() for line in (certificate.remarks_recommendations or '').split('\n') if line.strip()
    ][:7]
    while len(diagnosis_lines) < 5:
        diagnosis_lines.append('')
    while len(remarks_lines) < 7:
        remarks_lines.append('')

    return render(
        request,
        'document_request/preview_medical_certificate.html',
        {
            'medical_certificate': certificate,
            'certificate': certificate,
            'linked_doc_request': linked_doc_request,
            'issue_date': certificate.certificate_date,
            'physician_signature': physician_signature,
            'diagnosis_lines': diagnosis_lines or [''],
            'remarks_lines': remarks_lines or [''],
        },
    )


@login_required
@role_required(*_DOCUMENT_REQUEST_ACCESS_ROLES)
def download_medical_certificate_pdf(request, cert_id):
    certificate = get_object_or_404(MedicalCertificate, id=cert_id)
    try:
        _ensure_certificate_access(request.user, certificate)
    except PermissionDenied:
        messages.error(request, 'Access denied')
        return redirect('document_request:document_requests')

    linked_doc_request = (
        certificate.document_request
        or DocumentRequest.objects.filter(medical_certificate=certificate).first()
    )
    try:
        if linked_doc_request:
            assert_can_download_pdf(linked_doc_request, certificate)
        elif certificate.status != MedicalCertificate.Status.ISSUED:
            raise InvalidTransitionError('Certificate must be issued before downloading PDF.')
    except InvalidTransitionError as exc:
        messages.error(request, exc.message)
        return redirect('document_request:preview_medical_certificate', cert_id=cert_id)

    try:
        pdf_bytes = get_or_create_certificate_pdf_bytes(certificate)
    except PdfGenerationError as exc:
        messages.error(request, exc.message)
        return redirect('document_request:preview_medical_certificate', cert_id=cert_id)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="certificate_{certificate.id}.pdf"'
    return response
