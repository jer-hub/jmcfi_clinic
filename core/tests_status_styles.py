from django.test import SimpleTestCase

from core.status_styles import (
    APPOINTMENT_STATUS_VARIANTS,
    CALENDAR_FILTER_CHIP_TONES,
    appointment_status_variant,
    calendar_filter_chip_class,
    document_request_status_variant,
)


class StatusStylesTests(SimpleTestCase):
    def test_appointment_status_variants_match_calendar_semantics(self):
        self.assertEqual(APPOINTMENT_STATUS_VARIANTS['pending'], 'warning')
        self.assertEqual(APPOINTMENT_STATUS_VARIANTS['confirmed'], 'success')
        self.assertEqual(APPOINTMENT_STATUS_VARIANTS['completed'], 'muted')
        self.assertEqual(APPOINTMENT_STATUS_VARIANTS['cancelled'], 'danger')

    def test_appointment_status_variant_unknown_defaults_muted(self):
        self.assertEqual(appointment_status_variant('unknown'), 'muted')

    def test_document_completed_uses_muted(self):
        self.assertEqual(document_request_status_variant('completed'), 'muted')
        self.assertEqual(document_request_status_variant('pending_review'), 'warning')

    def test_calendar_filter_chip_active_inactive(self):
        inactive, active = CALENDAR_FILTER_CHIP_TONES['pending']
        self.assertEqual(calendar_filter_chip_class('pending', active=False), inactive)
        self.assertEqual(calendar_filter_chip_class('pending', active=True), active)
