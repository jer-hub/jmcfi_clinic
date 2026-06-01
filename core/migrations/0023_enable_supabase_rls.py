"""Enable RLS on public tables when using Supabase Postgres (PostgREST hardening)."""

from pathlib import Path

from django.db import migrations


def _sql_path():
    return Path(__file__).resolve().parent.parent / 'sql' / 'enable_supabase_rls.sql'


def enable_supabase_rls(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    sql = _sql_path().read_text(encoding='utf-8')
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(sql)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_collegedepartment_course_optional'),
    ]

    operations = [
        migrations.RunPython(enable_supabase_rls, noop_reverse),
    ]
