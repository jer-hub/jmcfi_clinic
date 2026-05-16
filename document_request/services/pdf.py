"""PDF generation and caching for issued medical certificates."""

from __future__ import annotations

from pathlib import Path

import pdfkit
from django.conf import settings
from django.core.files.base import ContentFile
from django.template.loader import render_to_string

from document_request.models import MedicalCertificate

from .errors import PdfGenerationError
from .selectors import get_certificate_signature_display


def resolve_wkhtmltopdf_path() -> str | None:
    configured = getattr(settings, 'WKHTMLTOPDF_CMD', '') or ''
    if configured and Path(configured).exists():
        return configured
    return None


def _build_pdf_context(certificate: MedicalCertificate) -> dict:
    physician_signature = get_certificate_signature_display(certificate)
    diagnosis_lines = [line.strip() for line in (certificate.diagnosis or '').split('\n') if line.strip()]
    remarks_lines = [
        line.strip() for line in (certificate.remarks_recommendations or '').split('\n') if line.strip()
    ]

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
        except OSError:
            physician_signature_uri = ''
    elif certificate.signature_snapshot:
        try:
            snap_path = Path(certificate.signature_snapshot.path)
            if snap_path.exists():
                physician_signature_uri = snap_path.resolve().as_uri()
        except OSError:
            physician_signature_uri = ''

    return {
        'certificate': certificate,
        'physician_signature': physician_signature,
        'diagnosis_lines': diagnosis_lines,
        'remarks_lines': remarks_lines,
        'is_pdf': True,
        'old_english_font_uri': old_english_font_uri,
        'physician_signature_uri': physician_signature_uri,
    }


def render_certificate_pdf_bytes(certificate: MedicalCertificate) -> bytes:
    wkhtmltopdf_path = resolve_wkhtmltopdf_path()
    if not wkhtmltopdf_path:
        raise PdfGenerationError(
            'wkhtmltopdf not found. Install it or set WKHTMLTOPDF_CMD in settings.'
        )

    html_string = render_to_string(
        'document_request/certificate_pdf.html',
        _build_pdf_context(certificate),
    )
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
    return pdfkit.from_string(html_string, False, options=options, configuration=config)


def generate_and_store_certificate_pdf(certificate: MedicalCertificate) -> MedicalCertificate:
    """Generate PDF bytes and store on certificate.issued_pdf."""
    pdf_bytes = render_certificate_pdf_bytes(certificate)
    filename = f'certificate_{certificate.pk}.pdf'
    certificate.issued_pdf.save(filename, ContentFile(pdf_bytes), save=True)
    return certificate


def get_or_create_certificate_pdf_bytes(certificate: MedicalCertificate) -> bytes:
    if certificate.issued_pdf:
        try:
            with certificate.issued_pdf.open('rb') as stored:
                return stored.read()
        except OSError:
            pass
    return render_certificate_pdf_bytes(certificate)
