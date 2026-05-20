"""Send pharmacy low-stock and expiry alerts to staff."""

from django.core.management.base import BaseCommand

from pharmacy.services.alerts import run_inventory_alerts
from pharmacy.services.stock_snapshot import refresh_all_medicine_stock_caches


class Command(BaseCommand):
    help = 'Refresh medicine stock caches and notify staff about inventory alerts.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report alert counts without sending notifications.',
        )
        parser.add_argument(
            '--skip-cache-refresh',
            action='store_true',
            help='Skip stock cache refresh before evaluating alerts.',
        )
        parser.add_argument(
            '--near-expiry-days',
            type=int,
            default=90,
            help='Days ahead to treat batches as near expiry (default: 90).',
        )

    def handle(self, *args, **options):
        if not options['skip_cache_refresh']:
            updated = refresh_all_medicine_stock_caches(active_only=False)
            self.stdout.write(self.style.SUCCESS(f'Refreshed stock cache for {updated} medicine(s).'))

        stats = run_inventory_alerts(
            near_expiry_days=options['near_expiry_days'],
            dry_run=options['dry_run'],
        )
        mode = 'DRY RUN' if stats['dry_run'] else 'SENT'
        self.stdout.write(
            f'{mode}: low stock={stats["low_stock_medicines"]}, '
            f'near expiry={stats["near_expiry_batches"]}, '
            f'expired={stats["expired_batches"]}, '
            f'notifications={stats["notifications_sent"]}'
        )
