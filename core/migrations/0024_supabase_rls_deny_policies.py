"""Add explicit deny-all RLS policies for Supabase API roles (linter 0008)."""

from pathlib import Path

from django.db import migrations


def _sql_path():
    return Path(__file__).resolve().parent.parent / 'sql' / 'enable_supabase_rls.sql'


def apply_supabase_rls(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    sql = _sql_path().read_text(encoding='utf-8')
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(sql)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_enable_supabase_rls'),
    ]

    operations = [
        migrations.RunPython(apply_supabase_rls, noop_reverse),
    ]
