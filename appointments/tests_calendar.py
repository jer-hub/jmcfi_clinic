from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import StudentProfile
from core.tests import _complete_staff_like_profile

from appointments.calendar_service import (
    ALL_STATUS_CHOICES,
    CalendarFilters,
    build_admin_calendar_context,
    build_calendar_body_context,
    build_calendar_context,
    build_calendar_day_context,
    build_calendar_filters_context,
    build_calendar_month_context,
    build_calendar_nav_urls,
    build_calendar_week_context,
    build_dashboard_calendar_context,
    build_ics_calendar,
    calendar_queryset,
    get_combined_events_by_date,
    get_events_by_date,
    month_bounds,
    parse_calendar_filters,
    schedule_appointment_url_for_date,
    statuses_for_filter,
    week_bounds,
)
from document_request.models import DocumentRequest
from appointments.models import Appointment

User = get_user_model()


def _complete_student_profile(user):
    user.first_name = user.first_name or 'Test'
    user.last_name = user.last_name or 'Student'
    user.save(update_fields=['first_name', 'last_name'])
    profile = user.patient_profile
    profile.patient_id = f'STU-CAL-{user.pk}'
    profile.middle_name = 'M'
    profile.gender = 'male'
    profile.civil_status = 'single'
    profile.date_of_birth = date(2000, 1, 1)
    profile.place_of_birth = 'City'
    profile.age = 24
    profile.address = '123 St'
    profile.phone = '+639171234567'
    profile.emergency_contact = 'Parent'
    profile.emergency_phone = '+639181234567'
    profile.department = 'College'
    profile.course = 'BS Test'
    profile.year_level = '1st Year'
    profile.blood_type = 'O+'
    profile.save()
    user.__dict__.pop('patient_profile', None)
    user._state.fields_cache.pop('patient_profile', None)


class CalendarServiceTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            email='cal-student@jmcfi.edu.ph',
            password='pass',
            role='patient',
            first_name='Cal',
            last_name='Student',
        )
        self.doctor = User.objects.create_user(
            email='cal-doctor@jmcfi.edu.ph',
            password='pass',
            role='doctor',
            first_name='Cal',
            last_name='Doctor',
        )
        self.other_doctor = User.objects.create_user(
            email='cal-doctor2@jmcfi.edu.ph',
            password='pass',
            role='doctor',
            first_name='Other',
            last_name='Doctor',
        )
        self.staff = User.objects.create_user(
            email='cal-staff@jmcfi.edu.ph',
            password='pass',
            role='staff',
            first_name='Cal',
            last_name='Staff',
        )
        self.other_student = User.objects.create_user(
            email='cal-student2@jmcfi.edu.ph',
            password='pass',
            role='patient',
            first_name='Other',
            last_name='Student',
        )
        self.appt_date = date(2026, 5, 15)
        self.student_appt = Appointment.objects.create(
            patient=self.student,
            doctor=self.doctor,
            appointment_type='consultation',
            date=self.appt_date,
            time=time(10, 0),
            reason='Checkup',
            status='confirmed',
        )
        Appointment.objects.create(
            patient=self.other_student,
            doctor=self.other_doctor,
            appointment_type='dental',
            date=self.appt_date,
            time=time(14, 0),
            reason='Dental',
            status='pending',
        )

    def _filters(self, user, **kwargs):
        defaults = {
            'year': 2026,
            'month': 5,
            'selected_date': self.appt_date,
        }
        defaults.update(kwargs)
        return CalendarFilters(**defaults)

    def test_student_queryset_only_own_appointments(self):
        qs = calendar_queryset(self.student)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().pk, self.student_appt.pk)

    def test_doctor_queryset_only_assigned(self):
        qs = calendar_queryset(self.doctor)
        self.assertEqual(qs.count(), 1)

    def test_staff_queryset_clinic_wide(self):
        qs = calendar_queryset(self.staff)
        self.assertEqual(qs.count(), 2)

    def test_staff_doctor_filter(self):
        qs = calendar_queryset(self.staff, doctor_id=self.doctor.pk)
        self.assertEqual(qs.count(), 1)

    def test_status_filter_limits_day_events(self):
        filters = self._filters(self.student, status_filter='pending')
        events = build_calendar_day_context(self.student, filters)['calendar_day_events']
        self.assertEqual(len(events), 0)
        filters.status_filter = 'confirmed'
        events = build_calendar_day_context(self.student, filters)['calendar_day_events']
        self.assertEqual(len(events), 1)

    def test_statuses_for_filter(self):
        self.assertEqual(statuses_for_filter(None), ALL_STATUS_CHOICES)
        self.assertEqual(statuses_for_filter('all'), ALL_STATUS_CHOICES)
        self.assertEqual(statuses_for_filter('cancelled'), ('cancelled',))
        self.assertIn('cancelled', statuses_for_filter(None))
        self.assertEqual(statuses_for_filter('confirmed'), ('confirmed',))

    def test_all_filter_includes_cancelled_appointments(self):
        cancelled_date = date(2026, 5, 16)
        Appointment.objects.create(
            patient=self.student,
            doctor=self.doctor,
            appointment_type='consultation',
            date=cancelled_date,
            time=time(11, 0),
            reason='Cancelled visit',
            status='cancelled',
        )
        filters = self._filters(self.student, selected_date=cancelled_date, status_filter='all')
        events = build_calendar_day_context(self.student, filters)['calendar_day_events']
        appt_events = [e for e in events if e.get('event_kind') == 'appointment']
        self.assertEqual(len(appt_events), 1)
        self.assertEqual(appt_events[0]['status'], 'cancelled')

        filters.status_filter = 'cancelled'
        only_cancelled = build_calendar_day_context(self.student, filters)['calendar_day_events']
        self.assertEqual(len(only_cancelled), 1)

        filters.status_filter = 'confirmed'
        confirmed_only = build_calendar_day_context(self.student, filters)['calendar_day_events']
        self.assertEqual(len(confirmed_only), 0)

    def test_default_view_includes_confirmed_appointments(self):
        filters = self._filters(self.student)
        events = build_calendar_day_context(self.student, filters)['calendar_day_events']
        appt_events = [e for e in events if e.get('event_kind') == 'appointment']
        self.assertEqual(len(appt_events), 1)
        self.assertEqual(appt_events[0]['status'], 'confirmed')

    def test_default_day_panel_includes_cancelled(self):
        cancelled_date = date(2026, 5, 16)
        Appointment.objects.create(
            patient=self.student,
            doctor=self.doctor,
            appointment_type='consultation',
            date=cancelled_date,
            time=time(11, 0),
            reason='Cancelled visit',
            status='cancelled',
        )
        filters = self._filters(self.student, selected_date=cancelled_date)
        events = build_calendar_day_context(self.student, filters)['calendar_day_events']
        appt_events = [e for e in events if e.get('event_kind') == 'appointment']
        self.assertEqual(len(appt_events), 1)
        self.assertEqual(appt_events[0]['status'], 'cancelled')
        self.assertEqual(appt_events[0]['variant'], 'danger')

    def test_week_badge_matches_day_panel_with_status_filter(self):
        cancelled_date = date(2026, 5, 18)
        for hour in (9, 10, 11):
            Appointment.objects.create(
                patient=self.other_student,
                doctor=self.doctor,
                appointment_type='consultation',
                date=cancelled_date,
                time=time(hour, 0),
                reason='Cancelled',
                status='cancelled',
            )
        filters = self._filters(
            self.staff,
            selected_date=cancelled_date,
            view_mode='week',
            status_filter='cancelled',
        )
        week_ctx = build_calendar_week_context(self.staff, filters)
        day_ctx = build_calendar_day_context(self.staff, filters)
        mon = next(
            d for d in week_ctx['calendar_week_days']
            if d['iso'] == cancelled_date.isoformat()
        )
        self.assertEqual(mon['event_count'], len(day_ctx['calendar_day_events']))
        self.assertEqual(mon['event_count'], 3)

    def test_month_context_includes_selected_day_events(self):
        ctx = build_calendar_month_context(self.student, self._filters(self.student))
        self.assertEqual(ctx['calendar_month_label'], 'May 2026')
        flat = [cell for week in ctx['calendar_weeks'] for cell in week]
        selected_cells = [c for c in flat if c['is_selected']]
        self.assertEqual(len(selected_cells), 1)
        self.assertEqual(selected_cells[0]['event_count'], 1)

    def test_cancelled_appears_in_month_grid_without_status_filter(self):
        cancelled_date = date(2026, 5, 17)
        Appointment.objects.create(
            patient=self.student,
            doctor=self.doctor,
            appointment_type='consultation',
            date=cancelled_date,
            time=time(11, 30),
            reason='No show',
            status='cancelled',
        )
        filters = self._filters(self.student, selected_date=cancelled_date)
        month_ctx = build_calendar_month_context(self.student, filters)
        flat = [cell for week in month_ctx['calendar_weeks'] for cell in week]
        cell = next(c for c in flat if c['iso'] == cancelled_date.isoformat())
        appt_events = [e for e in cell['events'] if e.get('event_kind') == 'appointment']
        self.assertEqual(cell['event_count'], 1)
        self.assertEqual(len(appt_events), 1)
        self.assertEqual(appt_events[0]['status'], 'cancelled')
        self.assertEqual(appt_events[0]['variant'], 'danger')
        self.assertEqual(appt_events[0]['status'], cell['visible_events'][0]['status'])

    def test_cancelled_appears_in_week_grid_without_status_filter(self):
        cancelled_date = date(2026, 5, 18)
        Appointment.objects.create(
            patient=self.student,
            doctor=self.doctor,
            appointment_type='consultation',
            date=cancelled_date,
            time=time(15, 0),
            reason='Cancelled',
            status='cancelled',
        )
        filters = self._filters(
            self.doctor,
            selected_date=cancelled_date,
            view_mode='week',
        )
        week_ctx = build_calendar_week_context(self.doctor, filters)
        day = next(
            d for d in week_ctx['calendar_week_days']
            if d['iso'] == cancelled_date.isoformat()
        )
        appt_events = [e for e in day['events'] if e.get('event_kind') == 'appointment']
        self.assertEqual(day['event_count'], 1)
        self.assertEqual(len(appt_events), 1)
        self.assertEqual(appt_events[0]['status'], 'cancelled')
        self.assertEqual(appt_events[0]['variant'], 'danger')

    def test_admin_heatmap_counts(self):
        ctx = build_admin_calendar_context(year=2026, month=5, selected_date=self.appt_date)
        flat = [cell for week in ctx['admin_calendar_weeks'] for cell in week]
        may15 = next(c for c in flat if c['day'] == 15 and c['in_month'])
        self.assertEqual(may15['event_count'], 2)
        self.assertGreater(may15['heat_level'], 0)

    def test_admin_heatmap_selected_day_events(self):
        admin = User.objects.create_user(
            email='admin-cal-detail@test.com',
            password='AdminPass123!',
            role='admin',
            is_staff=True,
            is_active=True,
        )
        ctx = build_admin_calendar_context(
            year=2026,
            month=5,
            selected_date=self.appt_date,
            user=admin,
        )
        self.assertEqual(len(ctx['admin_calendar_day_events']), 2)
        self.assertEqual(ctx['admin_calendar_selected_count'], 2)
        flat = [cell for week in ctx['admin_calendar_weeks'] for cell in week]
        may15 = next(c for c in flat if c['date'] == self.appt_date)
        self.assertTrue(may15['is_selected'])
        self.assertNotIn('select_url', may15)
        day_payload = ctx['admin_calendar_days_json']['2026-05-15']
        self.assertEqual(day_payload['appt_count'], 2)
        self.assertEqual(day_payload['count'], 2)
        self.assertEqual(len(day_payload['events']), 2)

    def test_admin_heatmap_includes_document_requests(self):
        admin = User.objects.create_user(
            email='admin-cal-docs@test.com',
            password='AdminPass123!',
            role='admin',
            is_staff=True,
            is_active=True,
        )
        doc = DocumentRequest.objects.create(
            patient=self.student,
            document_type='medical_certificate',
            purpose='Certificate',
            status=DocumentRequest.Status.PENDING_REVIEW,
        )
        doc_day = timezone.localtime(doc.created_at).date()
        ctx = build_admin_calendar_context(
            year=doc_day.year,
            month=doc_day.month,
            selected_date=doc_day,
            user=admin,
        )
        flat = [cell for week in ctx['admin_calendar_weeks'] for cell in week]
        day_cell = next(c for c in flat if c['date'] == doc_day)
        self.assertGreaterEqual(day_cell['document_count'], 1)
        payload = ctx['admin_calendar_days_json'][doc_day.isoformat()]
        self.assertGreaterEqual(payload['doc_count'], 1)
        doc_events = [e for e in payload['events'] if e.get('event_kind') == 'document']
        self.assertGreaterEqual(len(doc_events), 1)

    def test_admin_heatmap_excludes_cancelled(self):
        Appointment.objects.create(
            patient=self.student,
            doctor=self.doctor,
            appointment_type='consultation',
            date=self.appt_date,
            time=time(16, 0),
            reason='Cancelled',
            status='cancelled',
        )
        ctx = build_admin_calendar_context(year=2026, month=5, selected_date=self.appt_date)
        flat = [cell for week in ctx['admin_calendar_weeks'] for cell in week]
        may15 = next(c for c in flat if c['day'] == 15 and c['in_month'])
        self.assertEqual(may15['event_count'], 2)

    def test_dashboard_context_merges_month_and_day(self):
        ctx = build_dashboard_calendar_context(self.student, selected_date=self.appt_date)
        self.assertIn('calendar_weeks', ctx)
        self.assertIn('calendar_day_events', ctx)
        self.assertIn('calendar_status_chips', ctx)

    def test_status_chips_use_semantic_tones(self):
        filters = self._filters(self.student, status_filter='pending')
        chips = build_calendar_filters_context(self.student, filters)['calendar_status_chips']
        pending = next(c for c in chips if c['key'] == 'pending')
        confirmed = next(c for c in chips if c['key'] == 'confirmed')
        self.assertIn('bg-warning-100', pending['chip_class'])
        self.assertIn('border-warning-300', pending['chip_class'])
        self.assertIn('bg-success-50', confirmed['chip_class'])
        self.assertIn('border-success-200', confirmed['chip_class'])

    def test_event_kind_chips_present(self):
        filters = self._filters(self.student)
        chips = build_calendar_filters_context(self.student, filters)['calendar_event_chips']
        self.assertEqual([chip['key'] for chip in chips], ['all', 'appointments', 'documents'])
        self.assertEqual(sum(1 for chip in chips if chip['active']), 1)

    def test_all_items_chip_clears_status_filter(self):
        filters = self._filters(self.student, status_filter='cancelled')
        chips = build_calendar_filters_context(self.student, filters)['calendar_event_chips']
        all_chip = next(chip for chip in chips if chip['key'] == 'all')
        docs_chip = next(chip for chip in chips if chip['key'] == 'documents')
        appt_chip = next(chip for chip in chips if chip['key'] == 'appointments')
        self.assertNotIn('status=', all_chip['url'])
        self.assertNotIn('status=', docs_chip['url'])
        self.assertIn('status=cancelled', appt_chip['url'])

    def test_week_context_for_doctor(self):
        filters = self._filters(self.doctor, view_mode='week')
        ctx = build_calendar_week_context(self.doctor, filters)
        self.assertEqual(len(ctx['calendar_week_days']), 7)
        self.assertIn('–', ctx['calendar_period_label'])

    def test_patient_sees_week_view_toggle(self):
        filters = self._filters(self.student)
        ctx = build_calendar_filters_context(self.student, filters)
        self.assertTrue(ctx['calendar_show_week_view'])
        self.assertIn('view=week', ctx['calendar_view_week_url'])

    def test_week_body_context_for_patient(self):
        filters = self._filters(self.student, view_mode='week')
        ctx = build_calendar_body_context(self.student, filters)
        self.assertEqual(ctx['calendar_view_mode'], 'week')
        self.assertEqual(len(ctx['calendar_week_days']), 7)

    def test_month_nav_today_uses_today_date(self):
        filters = self._filters(self.doctor, selected_date=date(2026, 5, 15))
        today = timezone.localdate()
        nav = build_calendar_nav_urls(filters)
        self.assertIn(f'date={today.isoformat()}', nav['today'])

    def test_week_nav_preserves_view_and_steps_seven_days(self):
        anchor = date(2026, 5, 15)
        filters = self._filters(self.doctor, selected_date=anchor, view_mode='week')
        nav = build_calendar_nav_urls(filters)
        self.assertIn('view=week', nav['prev'])
        self.assertIn('view=week', nav['next'])
        self.assertIn(f'date={(anchor - timedelta(days=7)).isoformat()}', nav['prev'])
        self.assertIn(f'date={(anchor + timedelta(days=7)).isoformat()}', nav['next'])

    def test_nav_preserves_event_kind_filter(self):
        filters = self._filters(self.doctor, event_filter='documents')
        nav = build_calendar_nav_urls(filters)
        self.assertIn('kind=documents', nav['prev'])
        self.assertIn('kind=documents', nav['next'])
        self.assertIn('kind=documents', nav['today'])

    def test_week_period_label_is_range_not_month_only(self):
        filters = self._filters(self.doctor, selected_date=date(2026, 5, 15), view_mode='week')
        ctx = build_calendar_week_context(self.doctor, filters)
        self.assertNotEqual(ctx['calendar_period_label'], 'May 2026')
        week_start, week_end = week_bounds(date(2026, 5, 15))
        self.assertIn(str(week_start.day), ctx['calendar_period_label'])
        self.assertIn(str(week_end.year), ctx['calendar_period_label'])

    def test_document_events_merged_for_student(self):
        DocumentRequest.objects.create(
            patient=self.student,
            document_type='dental_record',
            purpose='Need copy',
            status=DocumentRequest.Status.PENDING_REVIEW,
        )
        start, end = month_bounds(2026, 5)
        events = get_combined_events_by_date(self.student, start, end)
        doc_days = [d for d, items in events.items() if any(e['event_kind'] == 'document' for e in items)]
        self.assertTrue(doc_days)

    def test_document_kind_filter_returns_only_document_events(self):
        doc = DocumentRequest.objects.create(
            patient=self.student,
            document_type='medical_certificate',
            purpose='Need certificate',
            status=DocumentRequest.Status.PENDING_REVIEW,
        )
        doc_day = timezone.localtime(doc.created_at).date()
        Appointment.objects.create(
            patient=self.student,
            doctor=self.doctor,
            appointment_type='consultation',
            date=doc_day,
            time=time(9, 0),
            reason='Same day visit',
            status='confirmed',
        )
        filters = self._filters(self.student, selected_date=doc_day, event_filter='documents')
        events = build_calendar_day_context(self.student, filters)['calendar_day_events']
        self.assertTrue(events)
        self.assertTrue(all(event['event_kind'] == 'document' for event in events))

    def test_appointments_kind_filter_returns_only_appointment_events(self):
        doc = DocumentRequest.objects.create(
            patient=self.student,
            document_type='medical_certificate',
            purpose='Need certificate',
            status=DocumentRequest.Status.PENDING_REVIEW,
        )
        doc_day = timezone.localtime(doc.created_at).date()
        Appointment.objects.create(
            patient=self.student,
            doctor=self.doctor,
            appointment_type='consultation',
            date=doc_day,
            time=time(11, 0),
            reason='Same day visit',
            status='confirmed',
        )
        filters = self._filters(self.student, selected_date=doc_day, event_filter='appointments')
        events = build_calendar_day_context(self.student, filters)['calendar_day_events']
        self.assertTrue(events)
        self.assertTrue(all(event['event_kind'] == 'appointment' for event in events))

    def test_ics_export_contains_appointment(self):
        filters = self._filters(self.student)
        ics = build_ics_calendar(self.student, filters)
        self.assertIn('BEGIN:VCALENDAR', ics)
        self.assertIn('BEGIN:VEVENT', ics)
        self.assertIn(f'appt-{self.student_appt.pk}@jmcfi-clinic', ics)

    def test_schedule_url_includes_date(self):
        url = schedule_appointment_url_for_date(self.appt_date)
        self.assertIn(f'date={self.appt_date.isoformat()}', url)


class CalendarViewTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            email='cal-view-student@jmcfi.edu.ph',
            password='pass',
            role='patient',
        )
        _complete_student_profile(self.student)
        self.doctor = User.objects.create_user(
            email='cal-view-doctor@jmcfi.edu.ph',
            password='pass',
            role='doctor',
        )
        _complete_staff_like_profile(self.doctor, 'DOC-CAL-001')
        profile = self.doctor.staff_profile
        profile.position = 'Physician'
        profile.license_number = 'LIC-001'
        profile.ptr_no = 'PTR-001'
        profile.save()
        self.staff = User.objects.create_user(
            email='cal-view-staff@jmcfi.edu.ph',
            password='pass',
            role='staff',
        )
        _complete_staff_like_profile(self.staff, 'STF-CAL-001')

    def test_month_fragment_requires_login(self):
        url = reverse('appointments:calendar_month_fragment')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_month_fragment_returns_partial(self):
        self.client.force_login(self.student)
        url = reverse('appointments:calendar_month_fragment')
        response = self.client.get(
            url,
            {'year': timezone.localdate().year, 'month': timezone.localdate().month},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'components/calendar/_calendar_body.html')

    def test_full_page_calendar(self):
        self.client.force_login(self.doctor)
        url = reverse('appointments:appointment_calendar')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'appointments/calendar.html')

    def test_full_page_hides_expand_link(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse('appointments:appointment_calendar'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '>Expand<')
        self.assertNotContains(response, 'up-right-and-down-left-from-center')

    def test_full_page_sets_push_url_on_month_nav(self):
        self.client.force_login(self.doctor)
        url = reverse('appointments:calendar_month_fragment')
        today = timezone.localdate()
        response = self.client.get(
            url,
            {'year': today.year, 'month': today.month, 'full': '1'},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('HX-Push-Url', response)

    def test_day_fragment_returns_partial(self):
        self.client.force_login(self.doctor)
        url = reverse('appointments:calendar_day_fragment')
        today = timezone.localdate()
        response = self.client.get(
            url,
            {'date': today.isoformat()},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'components/calendar/_day_agenda.html')

    def test_staff_doctor_filter_in_context(self):
        self.client.force_login(self.staff)
        url = reverse('appointments:calendar_month_fragment')
        response = self.client.get(
            url,
            {'year': 2026, 'month': 5, 'doctor': self.doctor.pk},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'cal-doctor-filter')

    def test_week_fragment_for_doctor(self):
        self.client.force_login(self.doctor)
        url = reverse('appointments:calendar_body_fragment')
        response = self.client.get(
            url,
            {'year': 2026, 'month': 5, 'date': '2026-05-15', 'view': 'week'},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'components/calendar/_week_view.html')

    def test_week_fragment_for_patient(self):
        self.client.force_login(self.student)
        url = reverse('appointments:calendar_body_fragment')
        response = self.client.get(
            url,
            {'year': 2026, 'month': 5, 'date': '2026-05-15', 'view': 'week'},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="cal-view-mode-toggle"')
        self.assertTemplateUsed(response, 'components/calendar/_week_view.html')

    def test_body_fragment_oob_updates_period_nav(self):
        self.client.force_login(self.doctor)
        url = reverse('appointments:calendar_body_fragment')
        response = self.client.get(
            url,
            {'year': 2026, 'month': 5, 'date': '2026-05-15', 'view': 'week'},
            HTTP_HX_REQUEST='true',
        )
        self.assertContains(response, 'id="cal-period-nav"')
        self.assertContains(response, 'hx-swap-oob="outerHTML"')
        self.assertContains(response, 'May 10')
        self.assertContains(response, 'view=week')

    def test_month_nav_next_updates_period_label_oob(self):
        self.client.force_login(self.doctor)
        url = reverse('appointments:calendar_body_fragment')
        response = self.client.get(
            url,
            {'year': 2026, 'month': 5, 'date': '2026-05-15'},
            HTTP_HX_REQUEST='true',
        )
        self.assertContains(response, 'May 2026')
        next_url = build_calendar_nav_urls(
            CalendarFilters(
                year=2026,
                month=5,
                selected_date=date(2026, 5, 15),
                view_mode='month',
            )
        )['next']
        response = self.client.get(next_url, HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'June 2026')
        self.assertContains(response, 'hx-swap-oob="outerHTML"')

    def test_ics_export_download(self):
        self.client.force_login(self.student)
        url = reverse('appointments:calendar_export_ics')
        response = self.client.get(url, {'year': 2026, 'month': 5})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/calendar; charset=utf-8')
        self.assertIn(b'BEGIN:VCALENDAR', response.content)

    def test_schedule_prefills_date(self):
        self.client.force_login(self.student)
        url = reverse('appointments:schedule_appointment')
        response = self.client.get(url, {'date': '2026-05-20'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '2026-05-20')

    def test_admin_cannot_access_calendar_fragments(self):
        admin = User.objects.create_user(
            email='cal-admin@jmcfi.edu.ph',
            password='pass',
            role='admin',
            is_staff=True,
        )
        _complete_staff_like_profile(admin, 'ADM-CAL-001')
        self.client.force_login(admin)
        response = self.client.get(reverse('appointments:calendar_month_fragment'))
        self.assertIn(response.status_code, (403, 302))
