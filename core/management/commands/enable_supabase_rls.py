"""Re-apply Supabase RLS hardening on all public tables (Postgres only)."""

from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = (
        'Enable RLS and revoke anon/authenticated access on public tables. '
        'Run after migrate when using Supabase Postgres.'
    )

    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            self.stdout.write(self.style.WARNING('Skipped: not using PostgreSQL.'))
            return

        sql_path = Path(__file__).resolve().parents[2] / 'sql' / 'enable_supabase_rls.sql'
        sql = sql_path.read_text(encoding='utf-8')
        with connection.cursor() as cursor:
            cursor.execute(sql)

        self.stdout.write(self.style.SUCCESS('Supabase RLS hardening applied to public tables.'))
