"""Export / import academic catalog (colleges, courses, year levels) between SQLite and Postgres."""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import CollegeDepartment, CourseProgram, YearLevelOption

CATALOG_VERSION = 1


def _configure_sqlite_alias(sqlite_path: Path) -> str:
    if not sqlite_path.is_file():
        raise CommandError(f'SQLite database not found: {sqlite_path}')
    base = settings.DATABASES.get('default', {}).copy()
    if base.get('ENGINE') != 'django.db.backends.sqlite3':
        base = {
            'ENGINE': 'django.db.backends.sqlite3',
            'ATOMIC_REQUESTS': False,
            'AUTOCOMMIT': True,
            'CONN_MAX_AGE': 0,
            'CONN_HEALTH_CHECKS': False,
            'OPTIONS': {},
            'TIME_ZONE': None,
        }
    base['NAME'] = str(sqlite_path)
    settings.DATABASES['sqlite_source'] = base
    return 'sqlite_source'


def _export_payload(db_alias: str) -> dict:
    colleges = list(
        CollegeDepartment.objects.using(db_alias)
        .order_by('name')
        .values('name', 'course_optional', 'is_active')
    )
    courses = [
        {
            'college': row.college_department.name,
            'name': row.name,
            'is_active': row.is_active,
        }
        for row in CourseProgram.objects.using(db_alias)
        .select_related('college_department')
        .order_by('college_department__name', 'name')
    ]
    year_levels = [
        {
            'college': row.college_department.name,
            'name': row.name,
            'sort_order': row.sort_order,
            'is_active': row.is_active,
        }
        for row in YearLevelOption.objects.using(db_alias)
        .select_related('college_department')
        .order_by('college_department__name', 'sort_order', 'name')
    ]
    return {
        'version': CATALOG_VERSION,
        'colleges': colleges,
        'courses': courses,
        'year_levels': year_levels,
    }


def _import_payload(payload: dict, *, clear: bool) -> dict:
    if payload.get('version') != CATALOG_VERSION:
        raise CommandError(
            f'Unsupported dump version {payload.get("version")!r}; expected {CATALOG_VERSION}.'
        )

    colleges = payload.get('colleges') or []
    courses = payload.get('courses') or []
    year_levels = payload.get('year_levels') or []

    counts = {'colleges': 0, 'courses': 0, 'year_levels': 0}

    with transaction.atomic():
        if clear:
            YearLevelOption.objects.all().delete()
            CourseProgram.objects.all().delete()
            CollegeDepartment.objects.all().delete()

        college_by_name = {}
        for row in colleges:
            name = (row.get('name') or '').strip()
            if not name:
                continue
            college, _created = CollegeDepartment.objects.update_or_create(
                name=name,
                defaults={
                    'course_optional': bool(row.get('course_optional', False)),
                    'is_active': bool(row.get('is_active', True)),
                },
            )
            college_by_name[name] = college
            counts['colleges'] += 1

        for row in courses:
            college_name = (row.get('college') or '').strip()
            course_name = (row.get('name') or '').strip()
            if not college_name or not course_name:
                continue
            college = college_by_name.get(college_name)
            if college is None:
                college = CollegeDepartment.objects.filter(name=college_name).first()
            if college is None:
                raise CommandError(f'Unknown college for course: {college_name!r}')
            CourseProgram.objects.update_or_create(
                college_department=college,
                name=course_name,
                defaults={'is_active': bool(row.get('is_active', True))},
            )
            counts['courses'] += 1

        for row in year_levels:
            college_name = (row.get('college') or '').strip()
            level_name = (row.get('name') or '').strip()
            if not college_name or not level_name:
                continue
            college = college_by_name.get(college_name)
            if college is None:
                college = CollegeDepartment.objects.filter(name=college_name).first()
            if college is None:
                raise CommandError(f'Unknown college for year level: {college_name!r}')
            YearLevelOption.objects.update_or_create(
                college_department=college,
                name=level_name,
                defaults={
                    'sort_order': int(row.get('sort_order') or 0),
                    'is_active': bool(row.get('is_active', True)),
                },
            )
            counts['year_levels'] += 1

    return counts


class Command(BaseCommand):
    help = (
        'Export or import the academic catalog (colleges, courses, year levels). '
        'Use export with --sqlite to read local db.sqlite3, then import with DATABASE_URL '
        'pointing at Supabase after migrate.'
    )

    def add_arguments(self, parser):
        sub = parser.add_subparsers(dest='action', required=True)

        export_parser = sub.add_parser(
            'export',
            help='Write catalog JSON from the database (SQLite by default).',
        )
        export_parser.add_argument(
            '-o',
            '--output',
            default='data/academic_catalog.json',
            help='Output JSON path (default: data/academic_catalog.json).',
        )
        export_parser.add_argument(
            '--sqlite',
            default='db.sqlite3',
            help='SQLite file to read when --from-sqlite is set (default: db.sqlite3).',
        )
        export_parser.add_argument(
            '--from-sqlite',
            action='store_true',
            help='Read from --sqlite even if DATABASE_URL is configured.',
        )
        export_parser.add_argument(
            '--database',
            default='default',
            help='Django DB alias when not using --from-sqlite (default: default).',
        )

        import_parser = sub.add_parser(
            'import',
            help='Load catalog JSON into the active database (Supabase when DATABASE_URL is set).',
        )
        import_parser.add_argument(
            '-i',
            '--input',
            default='data/academic_catalog.json',
            help='Input JSON path (default: data/academic_catalog.json).',
        )
        import_parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete existing catalog rows before import (courses, year levels, then colleges).',
        )

    def handle(self, *args, **options):
        action = options['action']
        if action == 'export':
            self._handle_export(options)
        elif action == 'import':
            self._handle_import(options)

    def _handle_export(self, options):
        if options['from_sqlite']:
            db_alias = _configure_sqlite_alias(Path(options['sqlite']))
            source = f'SQLite ({Path(options["sqlite"]).resolve()})'
        else:
            db_alias = options['database']
            source = f'database alias {db_alias!r}'

        payload = _export_payload(db_alias)
        output = Path(options['output'])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')

        self.stdout.write(
            self.style.SUCCESS(
                f'Exported academic catalog from {source} to {output.resolve()}: '
                f'{len(payload["colleges"])} colleges, '
                f'{len(payload["courses"])} courses, '
                f'{len(payload["year_levels"])} year levels.'
            )
        )

    def _handle_import(self, options):
        if settings.DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3':
            self.stdout.write(
                self.style.WARNING(
                    'Import target is SQLite. Set DATABASE_URL to your Supabase Postgres URL first.'
                )
            )

        input_path = Path(options['input'])
        if not input_path.is_file():
            raise CommandError(f'Dump file not found: {input_path}')

        payload = json.loads(input_path.read_text(encoding='utf-8'))
        counts = _import_payload(payload, clear=options['clear'])

        self.stdout.write(
            self.style.SUCCESS(
                f'Imported academic catalog from {input_path.resolve()}: '
                f'{counts["colleges"]} colleges, '
                f'{counts["courses"]} courses, '
                f'{counts["year_levels"]} year levels.'
            )
        )
