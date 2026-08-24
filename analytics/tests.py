from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import StaffProfile, User


def _staff_profile(user, staff_id):
    profile, _ = StaffProfile.objects.get_or_create(user=user)
    profile.staff_id = staff_id
    profile.department = 'Clinic Operations'
    profile.phone = '09123456789'
    profile.save()
    return profile


@override_settings(
    MIDDLEWARE=[
        m for m in settings.MIDDLEWARE
        if m != 'core.middleware.ProfileCompleteMiddleware'
    ],
)
class AnalyticsExportTests(TestCase):
    def setUp(self):
        self.doctor = User.objects.create_user(
            email='doctor-export@test.com',
            password='pass',
            role='doctor',
            is_staff=True,
            is_active=True,
            first_name='Export',
            last_name='Doctor',
        )
        _staff_profile(self.doctor, 'DOC-EXP-001')

        self.admin = User.objects.create_user(
            email='admin-export@test.com',
            password='pass',
            role='admin',
            is_staff=True,
            is_active=True,
            first_name='Export',
            last_name='Admin',
        )
        _staff_profile(self.admin, 'ADM-EXP-001')

    def test_staff_dashboard_export_for_doctor(self):
        self.client.force_login(self.doctor)
        url = reverse('analytics:export_report')
        response = self.client.get(url, {
            'report': 'staff_dashboard',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        body = response.content.decode()
        self.assertIn('Staff Analytics Dashboard', body)
        self.assertIn('Unique patients', body)

    def test_admin_dashboard_export_forbidden_for_doctor(self):
        self.client.force_login(self.doctor)
        url = reverse('analytics:export_report')
        response = self.client.get(url, {
            'report': 'admin_dashboard',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
        })
        self.assertEqual(response.status_code, 403)

    def test_staff_dashboard_page_includes_export_control(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse('analytics:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Export')
        self.assertContains(response, 'staff_dashboard')

    def test_health_trends_page_includes_export_menu(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse('analytics:health_trends'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'health_trends_summary')
        self.assertContains(response, 'health_trends_live')

    def test_health_trends_summary_export(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse('analytics:export_report'), {
            'report': 'health_trends_summary',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Health Trends', response.content.decode())

    def test_resource_utilization_page_includes_export_menu(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse('analytics:resource_utilization'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'resource_utilization_summary')
        self.assertContains(response, 'resource_utilization_staff')

    def test_resource_utilization_summary_export(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse('analytics:export_report'), {
            'report': 'resource_utilization_summary',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Resource Utilization', response.content.decode())

    def test_population_health_page_includes_export_menu(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse('analytics:population_health'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'population_summary')
        self.assertContains(response, 'population_period')

    def test_population_summary_export(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse('analytics:export_report'), {
            'report': 'population_summary',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Population Health', response.content.decode())

    def test_academic_page_includes_export_menu(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse('analytics:academic_correlation'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'academic_summary')
        self.assertContains(response, 'academic_visitors')

    def test_academic_summary_export(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse('analytics:export_report'), {
            'report': 'academic_summary',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Academic Correlation', response.content.decode())

    def test_financial_page_includes_export_menu(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('analytics:financial_overview'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'financial_summary')
        self.assertContains(response, 'report=financial&amp;')

    def test_financial_summary_export(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('analytics:export_report'), {
            'report': 'financial_summary',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        body = response.content.decode()
        self.assertIn('Financial & Cost Analysis', body)
        self.assertIn('Total expenses', body)
        self.assertIn('Expenses by category', body)
        self.assertIn('Monthly overview', body)

    def test_financial_records_export(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('analytics:export_report'), {
            'report': 'financial',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('Date', response.content.decode())

    def test_financial_export_forbidden_for_doctor(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse('analytics:export_report'), {
            'report': 'financial_summary',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
        })
        self.assertEqual(response.status_code, 403)

    def test_predictive_page_includes_export_menu(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse('analytics:predictive_analytics'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'predictive_insights')
        self.assertContains(response, 'predictive_hourly')

    def test_predictive_hourly_export(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse('analytics:export_report'), {
            'report': 'predictive_hourly',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Predictive hourly and weekday summary', response.content.decode())

    def test_compliance_index_export_for_admin(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('analytics:export_report'), {
            'report': 'compliance_index',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Compliance reports index', response.content.decode())


@override_settings(
    MIDDLEWARE=[
        m for m in settings.MIDDLEWARE
        if m != 'core.middleware.ProfileCompleteMiddleware'
    ],
)
class AcademicAnalyticsFilterTests(TestCase):
    def setUp(self):
        from datetime import date, time
        from decimal import Decimal

        from appointments.models import Appointment
        from core.models import PatientProfile
        from medical_records.models import MedicalRecord

        from analytics.models import FinancialRecord, HealthTrendRecord

        self.doctor = User.objects.create_user(
            email='doctor-filters@test.com',
            password='pass',
            role='doctor',
            is_staff=True,
            is_active=True,
            first_name='Filter',
            last_name='Doctor',
        )
        _staff_profile(self.doctor, 'DOC-FLT-001')

        self.admin = User.objects.create_user(
            email='admin-filters@test.com',
            password='pass',
            role='admin',
            is_staff=True,
            is_active=True,
            first_name='Filter',
            last_name='Admin',
        )
        _staff_profile(self.admin, 'ADM-FLT-001')

        self.nursing = User.objects.create_user(
            email='nursing@test.com',
            password='pass',
            role='patient',
            is_active=True,
            first_name='Nurse',
            last_name='Student',
        )
        nursing_profile, _ = PatientProfile.objects.get_or_create(
            user=self.nursing,
            defaults={'patient_id': 'NRS-001'},
        )
        nursing_profile.patient_id = 'NRS-001'
        nursing_profile.department = 'College of Nursing'
        nursing_profile.course = 'BS Nursing'
        nursing_profile.year_level = '1st Year'
        nursing_profile.save()
        self.business = User.objects.create_user(
            email='business@test.com',
            password='pass',
            role='patient',
            is_active=True,
            first_name='Biz',
            last_name='Student',
        )
        business_profile, _ = PatientProfile.objects.get_or_create(
            user=self.business,
            defaults={'patient_id': 'BUS-001'},
        )
        business_profile.patient_id = 'BUS-001'
        business_profile.department = 'College of Business'
        business_profile.course = 'BS Accountancy'
        business_profile.year_level = '2nd Year'
        business_profile.save()

        visit_date = date(2026, 8, 10)
        Appointment.objects.create(
            patient=self.nursing,
            doctor=self.doctor,
            appointment_type='consultation',
            date=visit_date,
            time=time(9, 0),
            reason='Checkup',
        )
        Appointment.objects.create(
            patient=self.business,
            doctor=self.doctor,
            appointment_type='consultation',
            date=visit_date,
            time=time(10, 0),
            reason='Checkup',
        )
        MedicalRecord.objects.create(
            patient=self.nursing,
            doctor=self.doctor,
            diagnosis='Flu',
            treatment='Rest',
        )
        MedicalRecord.objects.create(
            patient=self.business,
            doctor=self.doctor,
            diagnosis='Cold',
            treatment='Rest',
        )
        FinancialRecord.objects.create(
            category='other',
            description='Clinic-wide expense',
            amount=Decimal('150.00'),
            is_expense=True,
            date=visit_date,
            recorded_by=self.admin,
        )
        HealthTrendRecord.objects.create(
            academic_year='2025-2026',
            semester='1st',
            illness_category='Flu',
            case_count=4,
        )
        HealthTrendRecord.objects.create(
            academic_year='2025-2026',
            semester='2nd',
            illness_category='Dengue',
            case_count=2,
        )

    def test_get_academic_filters_parses_query(self):
        from django.test import RequestFactory

        from analytics.academic_filters import academic_filter_q, get_academic_filters

        request = RequestFactory().get('/', {
            'department': ' College of Nursing ',
            'course': '',
            'year_level': '1st Year',
        })
        filters = get_academic_filters(request)
        self.assertEqual(filters['department'], 'College of Nursing')
        self.assertEqual(filters['course'], '')
        self.assertEqual(filters['year_level'], '1st Year')
        q = academic_filter_q(filters)
        self.assertTrue(q.children)

    def test_course_and_year_ignored_without_department(self):
        from django.test import RequestFactory

        from analytics.academic_filters import get_academic_filters

        request = RequestFactory().get('/', {
            'course': 'BS Nursing',
            'year_level': '1st Year',
        })
        filters = get_academic_filters(request)
        self.assertEqual(filters['department'], '')
        self.assertEqual(filters['course'], '')
        self.assertEqual(filters['year_level'], '')

    def test_filter_bar_includes_cascading_script_and_catalog(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse('analytics:population_health'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('analyticsFilterBar()', body)
        self.assertIn('__jmcfiAnalyticsFilterCatalog', body)
        self.assertIn('coursesByCollege', body)
        self.assertIn('Select college first', body)
        self.assertContains(response, 'Apply')
        self.assertIn('disabled:bg-gray-50', body)
        self.assertRegex(body, r'/static/js/analytics_filter_bar(?:\.[a-f0-9]+)?\.js')

    def test_filter_bar_with_department_populates_program_options(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse('analytics:population_health'), {
            'department': 'College of Nursing',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'College of Nursing')
        self.assertContains(response, 'All programs')

    def test_filter_bar_config_preserves_course_and_year_level(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse('analytics:population_health'), {
            'department': 'College of Nursing',
            'course': 'BS Nursing',
            'year_level': '1st Year',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '"course": "BS Nursing"')
        self.assertContains(response, '"year_level": "1st Year"')

    def test_health_trends_has_no_school_term_and_term_param_ignored(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse('analytics:health_trends'), {
            'term': '2025-2026|1st',
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'School term')
        self.assertContains(response, 'Flu')
        self.assertContains(response, 'Dengue')

    def test_population_and_academic_pages_accept_academic_params(self):
        self.client.force_login(self.doctor)
        params = {
            'department': 'College of Nursing',
            'course': 'BS Nursing',
            'year_level': '1st Year',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
        }
        pop = self.client.get(reverse('analytics:population_health'), params)
        acad = self.client.get(reverse('analytics:academic_correlation'), params)
        self.assertEqual(pop.status_code, 200)
        self.assertEqual(acad.status_code, 200)
        self.assertContains(pop, 'Department')
        self.assertContains(acad, 'Department')

    def test_population_filter_scopes_to_matching_department(self):
        self.client.force_login(self.doctor)
        url = reverse('analytics:population_health')
        all_resp = self.client.get(url, {
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
        })
        filtered = self.client.get(url, {
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
            'department': 'College of Nursing',
        })
        self.assertEqual(all_resp.context['records_in_period'], 2)
        self.assertEqual(filtered.context['records_in_period'], 1)
        self.assertEqual(filtered.context['appt_in_period'], 1)

    def test_export_includes_academic_filter_header(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse('analytics:export_report'), {
            'report': 'population_summary',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
            'department': 'College of Nursing',
        })
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('Academic filters', body)
        self.assertIn('College of Nursing', body)

    def test_financial_page_keeps_totals_and_filters_clinical_snapshot(self):
        self.client.force_login(self.admin)
        url = reverse('analytics:financial_overview')
        unfiltered = self.client.get(url, {
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
        })
        filtered = self.client.get(url, {
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
            'department': 'College of Nursing',
        })
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(
            unfiltered.context['summary']['total_expenses'],
            filtered.context['summary']['total_expenses'],
        )
        self.assertEqual(unfiltered.context['filtered_appointments'], 2)
        self.assertEqual(filtered.context['filtered_appointments'], 1)
        self.assertEqual(filtered.context['filtered_medical_records'], 1)
        self.assertContains(filtered, 'clinic-wide')

    def test_pagination_query_includes_academic_type_and_illness(self):
        from datetime import date

        from django.test import RequestFactory

        from analytics.academic_filters import build_pagination_query, page_window_numbers

        request = RequestFactory().get('/', {
            'department': 'College of Nursing',
            'course': 'BS Nursing',
            'type': 'peak_hours',
            'illness_category': 'Flu',
        })
        query = build_pagination_query(date(2026, 1, 1), date(2026, 12, 31), request)
        self.assertIn('department=College', query)
        self.assertIn('course=BS%20Nursing', query)
        self.assertIn('type=peak_hours', query)
        self.assertIn('illness_category=Flu', query)
        self.assertIn('date_from=2026-01-01', query)

        class _FakePage:
            number = 5

            class paginator:
                num_pages = 10

        window = page_window_numbers(_FakePage())
        self.assertEqual(window[0], 1)
        self.assertEqual(window[-1], 10)
        self.assertIn('', window)

    def test_financial_and_resource_context_preserve_pagination_query(self):
        self.client.force_login(self.admin)
        params = {
            'department': 'College of Nursing',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
        }
        financial = self.client.get(reverse('analytics:financial_overview'), params)
        resources = self.client.get(reverse('analytics:resource_utilization'), params)
        self.assertEqual(financial.status_code, 200)
        self.assertEqual(resources.status_code, 200)
        self.assertIn('department=College', financial.context['pagination_query'])
        self.assertIn('department=College', resources.context['pagination_query'])
        self.assertContains(financial, 'Clear filters')
        self.assertContains(resources, 'Clinic-wide daily log')

    def test_chart_data_api_forbidden_for_patient(self):
        self.client.force_login(self.nursing)
        response = self.client.get(
            reverse('analytics:chart_data_api'),
            {'chart': 'appointment_volume'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 403)

    def test_chart_data_api_ok_for_staff_roles(self):
        self.client.force_login(self.doctor)
        response = self.client.get(
            reverse('analytics:chart_data_api'),
            {
                'chart': 'appointment_volume',
                'date_from': '2026-01-01',
                'date_to': '2026-12-31',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('labels', payload)
        self.assertIn('values', payload)

    def test_health_trends_illness_filter_affects_aggregate_and_live(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse('analytics:health_trends'), {
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
            'illness_category': 'Flu',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['trends_count'], 1)
        self.assertContains(response, 'Flu')
        self.assertNotContains(response, 'Dengue')
        self.assertContains(response, 'Clinic-wide historical')
        self.assertContains(response, 'Medical cases')
        self.assertContains(response, 'Dental cases')

    def test_academic_page_renders_chart_canvases(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse('analytics:academic_correlation'), {
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'visitsDeptChart')
        self.assertContains(response, 'visitsCourseChart')
        self.assertTrue(response.context['visits_by_department'])
        self.assertTrue(response.context['visits_by_course'])

    def test_compliance_list_filters_by_stored_academic_segment(self):
        from datetime import date

        from analytics.models import ComplianceReport

        self.client.force_login(self.admin)
        ComplianceReport.objects.create(
            report_type='ched',
            title='Nursing snapshot',
            period_start=date(2026, 1, 1),
            period_end=date(2026, 12, 31),
            generated_by=self.admin,
            data_json={'academic_filters': {'department': 'College of Nursing'}},
        )
        ComplianceReport.objects.create(
            report_type='ched',
            title='Business snapshot',
            period_start=date(2026, 1, 1),
            period_end=date(2026, 12, 31),
            generated_by=self.admin,
            data_json={'academic_filters': {'department': 'College of Business'}},
        )
        filtered = self.client.get(reverse('analytics:compliance_reports'), {
            'department': 'College of Nursing',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
        })
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(filtered.context['reports_total'], 1)
        self.assertContains(filtered, 'Nursing snapshot')
        self.assertNotContains(filtered, 'Business snapshot')

    def test_compliance_detail_shows_stored_academic_filters(self):
        from datetime import date

        from analytics.models import ComplianceReport

        self.client.force_login(self.admin)
        report = ComplianceReport.objects.create(
            report_type='ched',
            title='Stored filters report',
            period_start=date(2026, 1, 1),
            period_end=date(2026, 12, 31),
            generated_by=self.admin,
            data_json={
                'academic_filters': {
                    'department': 'College of Nursing',
                    'course': 'BS Nursing',
                    'year_level': '1st Year',
                },
                'total_appointments': 3,
            },
        )
        response = self.client.get(
            reverse('analytics:compliance_report_detail', args=[report.pk]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dept: College of Nursing')
        self.assertContains(response, 'Program: BS Nursing')
        self.assertContains(response, 'Year: 1st Year')
        self.assertContains(response, 'Appointments')

    def test_admin_dashboard_empty_chart_state(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('core:dashboard'), {
            'date_from': '2020-01-01',
            'date_to': '2020-01-31',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No appointment volume')

