import re

from django.template import Context
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase

from core.subnav_helpers import enrich_subnav, nav_dropdown, nav_group, nav_item
from core.templatetags.app_subnav import feedback_subnav, medical_records_subnav, pharmacy_subnav


class EnrichSubnavTests(SimpleTestCase):
    def test_breadcrumbs_when_sub_page_active(self):
        items = [
            {'label': 'Home', 'url': '/a/', 'icon': 'fa-home', 'active': False},
            {'label': 'Child', 'url': '/b/', 'icon': 'fa-child', 'active': True},
        ]
        ctx = enrich_subnav(items)
        self.assertTrue(ctx['show_breadcrumbs'])
        self.assertEqual(ctx['bc_crumbs'][0]['label'], 'Home')
        self.assertEqual(ctx['bc_crumbs'][1]['label'], 'Child')

    def test_single_item_hides_subnav_unless_always_show(self):
        items = [{'label': 'Inbox', 'url': '/messages/', 'icon': 'fa-inbox', 'active': True}]
        ctx = enrich_subnav(items)
        self.assertEqual(ctx['items'], [])
        self.assertFalse(ctx['show_breadcrumbs'])

        ctx_force = enrich_subnav(items, always_show_nav=True)
        self.assertEqual(len(ctx_force['items']), 1)

    def test_always_show_nav_skips_breadcrumbs(self):
        items = [
            {'label': 'Home', 'url': '/a/', 'active': False},
            {'label': 'Child', 'url': '/b/', 'active': True},
        ]
        ctx = enrich_subnav(items, always_show_nav=True)
        self.assertFalse(ctx['show_breadcrumbs'])
        self.assertEqual(len(ctx['items']), 2)

    def test_nav_item_builds_reverse_url(self):
        item = nav_item('Test', 'core:settings_hub', icon='fa-x', active=True)
        self.assertEqual(item['label'], 'Test')
        self.assertTrue(item['active'])
        self.assertIn('/settings', item['url'])

    def test_grouped_layout_for_multi_row_menus(self):
        ctx = enrich_subnav(
            groups=[
                nav_group('Catalog', [{'label': 'A', 'url': '/a/', 'active': True}]),
            ],
            always_show_nav=True,
            nav_aria_label='Pharmacy sections',
        )
        self.assertEqual(ctx['nav_layout'], 'grouped')
        self.assertEqual(len(ctx['groups']), 1)
        self.assertEqual(ctx['nav_aria_label'], 'Pharmacy sections')

    def test_dropdown_layout_for_pharmacy_style_menus(self):
        ctx = enrich_subnav(
            items=[{'label': 'Dashboard', 'url': '/pharmacy/', 'active': False}],
            dropdowns=[
                nav_dropdown(
                    'Catalog',
                    [{'label': 'Medicines', 'url': '/medicines/', 'active': True}],
                ),
            ],
            always_show_nav=True,
            nav_aria_label='Pharmacy sections',
        )
        self.assertEqual(len(ctx['items']), 1)
        self.assertEqual(len(ctx['dropdowns']), 1)
        self.assertTrue(ctx['dropdowns'][0]['active'])
        self.assertEqual(ctx['nav_aria_label'], 'Pharmacy sections')

    def test_nav_dropdown_active_when_child_active(self):
        dropdown = nav_dropdown(
            'Catalog',
            [
                {'label': 'A', 'url': '/a/', 'active': False},
                {'label': 'B', 'url': '/b/', 'active': True},
            ],
        )
        self.assertTrue(dropdown['active'])

    def test_nav_dropdown_accepts_icon(self):
        dropdown = nav_dropdown('Catalog', [], icon='fa-book-medical')
        self.assertEqual(dropdown['icon'], 'fa-book-medical')

    def test_nav_dropdown_always_includes_icon_key(self):
        dropdown = nav_dropdown('Catalog', [])
        self.assertIn('icon', dropdown)
        self.assertEqual(dropdown['icon'], '')

    def test_long_flat_menu_uses_wrapped_layout(self):
        items = [
            {'label': f'Tab {i}', 'url': f'/t{i}/', 'active': i == 0}
            for i in range(7)
        ]
        ctx = enrich_subnav(items, always_show_nav=True)
        self.assertEqual(ctx['nav_layout'], 'wrapped')


class PharmacySubnavTemplateTests(SimpleTestCase):
    def _pharmacy_context(self, view_name='pharmacy:dashboard'):
        request = RequestFactory().get('/pharmacy/')
        request.resolver_match = type(
            'M',
            (),
            {'view_name': view_name, 'kwargs': {}},
        )()
        request.user = type('U', (), {'role': 'staff'})()
        return pharmacy_subnav(Context({'request': request}))

    def test_pharmacy_dropdown_triggers_all_have_icons(self):
        ctx = self._pharmacy_context()
        expected = {
            'Catalog': 'fa-book-medical',
            'Supply': 'fa-truck-field',
            'Operations': 'fa-gears',
            'Records': 'fa-folder-open',
        }
        for dropdown in ctx['dropdowns']:
            self.assertEqual(dropdown['icon'], expected[dropdown['label']])

        html = render_to_string('components/sub_nav.html', ctx)
        triggers = re.findall(
            r'id="subnav-trigger-\d+".*?</button>',
            html,
            flags=re.DOTALL,
        )
        self.assertEqual(len(triggers), len(expected))
        for block in triggers:
            self.assertIn('nav-link-icon', block)

    def test_pharmacy_nav_uses_shared_wrapper_classes(self):
        ctx = self._pharmacy_context()
        html = render_to_string('components/sub_nav.html', ctx)
        self.assertIn('aria-label="Pharmacy sections"', html)
        self.assertIn('mb-6 w-full max-w-full', html)
        self.assertNotIn('overflow-x-auto', html)
        self.assertIn('overflow-visible', html)
        self.assertIn('role="tablist"', html)

    def test_pharmacy_dropdown_menus_render_alpine_flyouts(self):
        ctx = self._pharmacy_context()
        html = render_to_string('components/sub_nav.html', ctx)
        menus = re.findall(r'id="subnav-menu-\d+"', html)
        self.assertEqual(len(menus), 4)
        self.assertIn('x-data="{ open: false', html)
        self.assertIn('x-show="open"', html)
        self.assertIn('role="menu"', html)
        self.assertIn('absolute left-0 top-full z-50', html)


class FeedbackSubnavTemplateTests(SimpleTestCase):
    def _feedback_context(self, view_name='feedback:submit_feedback', *, role='patient'):
        request = RequestFactory().get('/feedback/submit/')
        request.resolver_match = type(
            'M',
            (),
            {'view_name': view_name, 'kwargs': {}},
        )()
        request.user = type('U', (), {'role': role})()
        return feedback_subnav(Context({'request': request}))

    def test_submit_page_keeps_tab_strip_not_breadcrumbs(self):
        ctx = self._feedback_context('feedback:submit_feedback')
        self.assertFalse(ctx['show_breadcrumbs'])
        self.assertEqual(len(ctx['items']), 2)
        self.assertTrue(ctx['items'][1]['active'])

    def test_staff_stats_tab_included(self):
        ctx = self._feedback_context('feedback:feedback_stats', role='staff')
        self.assertEqual(len(ctx['items']), 3)
        self.assertEqual(ctx['nav_aria_label'], 'Feedback sections')

    def test_feedback_nav_uses_shared_wrapper_classes(self):
        ctx = self._feedback_context()
        html = render_to_string('components/sub_nav.html', ctx)
        self.assertIn('aria-label="Feedback sections"', html)
        self.assertIn('role="tablist"', html)
        self.assertIn('class="nav-link whitespace-nowrap shrink-0 active"', html)


class MedicalRecordsSubnavTemplateTests(SimpleTestCase):
    def _medical_context(self, view_name='medical_records:medical_records', *, record=None):
        request = RequestFactory().get('/medical-records/')
        request.resolver_match = type(
            'M',
            (),
            {'view_name': view_name, 'kwargs': {}},
        )()
        request.user = type('U', (), {'role': 'doctor'})()
        ctx = {'request': request}
        if record is not None:
            ctx['record'] = record
        return medical_records_subnav(Context(ctx))

    def test_list_page_keeps_tab_strip(self):
        ctx = self._medical_context()
        self.assertFalse(ctx['show_breadcrumbs'])
        self.assertEqual(len(ctx['items']), 2)

    def test_detail_page_uses_breadcrumb_subnav(self):
        patient = type('P', (), {'get_full_name': lambda self: 'Jerwin Carreon'})()
        record = type(
            'R',
            (),
            {
                'patient': patient,
                'created_at': type('D', (), {'strftime': lambda self, fmt: 'Jul 07, 2026'})(),
            },
        )()
        ctx = self._medical_context('medical_records:medical_record_detail_page', record=record)
        self.assertTrue(ctx['show_breadcrumbs'])
        self.assertEqual(ctx['bc_crumbs'][0]['label'], 'Medical Records')
        self.assertEqual(ctx['bc_crumbs'][1]['label'], 'Jerwin Carreon — Jul 07, 2026')

        html = render_to_string('components/sub_nav.html', ctx)
        self.assertIn('aria-label="Breadcrumb"', html)
        self.assertIn('Jerwin Carreon — Jul 07, 2026', html)
        self.assertIn('text-[13px]', html)
