from django.test import SimpleTestCase

from core.subnav_helpers import enrich_subnav, nav_item


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
