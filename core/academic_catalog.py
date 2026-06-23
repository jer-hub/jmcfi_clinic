"""Shared helpers for college / course / year-level catalog data."""

from django.db import transaction

from .models import CollegeDepartment, CourseProgram, PatientProfile, YearLevelOption


def active_colleges_queryset():
    return CollegeDepartment.objects.filter(is_active=True).order_by('name')


def course_optional_by_college():
    """Map college name -> whether course/program is optional."""
    return dict(
        CollegeDepartment.objects.filter(is_active=True).values_list('name', 'course_optional')
    )


def is_course_optional_for_department(department_name):
    name = (department_name or '').strip()
    if not name:
        return False
    try:
        return CollegeDepartment.objects.get(name=name, is_active=True).course_optional
    except CollegeDepartment.DoesNotExist:
        return False


def courses_by_college(active_only=True):
    mapping = {}
    qs = CourseProgram.objects.select_related('college_department')
    if active_only:
        qs = qs.filter(is_active=True, college_department__is_active=True)
    for course in qs.order_by('college_department__name', 'name'):
        mapping.setdefault(course.college_department.name, []).append(course.name)
    return mapping


def year_levels_by_college(active_only=True):
    mapping = {}
    qs = YearLevelOption.objects.select_related('college_department')
    if active_only:
        qs = qs.filter(is_active=True, college_department__is_active=True)
    for item in qs.order_by('college_department__name', 'sort_order', 'name'):
        mapping.setdefault(item.college_department.name, []).append(item.name)
    return mapping


def college_catalog_counts():
    return {
        'colleges': CollegeDepartment.objects.filter(is_active=True).count(),
        'courses': CourseProgram.objects.filter(is_active=True, college_department__is_active=True).count(),
        'year_levels': YearLevelOption.objects.filter(
            is_active=True, college_department__is_active=True
        ).count(),
    }


def patient_department_usage_count(department_name: str) -> int:
    return PatientProfile.objects.filter(department=(department_name or '').strip()).count()


def patient_course_usage_count(college_name: str, course_name: str) -> int:
    return PatientProfile.objects.filter(
        department=(college_name or '').strip(),
        course=(course_name or '').strip(),
    ).count()


def patient_year_level_usage_count(college_name: str, year_level_name: str) -> int:
    return PatientProfile.objects.filter(
        department=(college_name or '').strip(),
        year_level=(year_level_name or '').strip(),
    ).count()


class CatalogDeleteError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


@transaction.atomic
def delete_course(course: CourseProgram) -> str:
    college_name = course.college_department.name
    course_name = course.name
    usage = patient_course_usage_count(college_name, course_name)
    if usage:
        raise CatalogDeleteError(
            f'Cannot delete "{course_name}" — {usage} patient profile(s) still use it.'
        )
    course.delete()
    return course_name


@transaction.atomic
def delete_year_level(year_level: YearLevelOption) -> str:
    college_name = year_level.college_department.name
    level_name = year_level.name
    usage = patient_year_level_usage_count(college_name, level_name)
    if usage:
        raise CatalogDeleteError(
            f'Cannot delete "{level_name}" — {usage} patient profile(s) still use it.'
        )
    year_level.delete()
    return level_name


@transaction.atomic
def delete_college(college: CollegeDepartment) -> tuple[str, int, int]:
    college_name = college.name
    usage = patient_department_usage_count(college_name)
    if usage:
        raise CatalogDeleteError(
            f'Cannot delete "{college_name}" — {usage} patient profile(s) still use it.'
        )
    course_count = college.course_programs.count()
    year_level_count = college.year_levels.count()
    college.course_programs.all().delete()
    college.year_levels.all().delete()
    college.delete()
    return college_name, course_count, year_level_count


def patient_catalog_context():
    """Template context fragments for patient college/course/year-level dropdowns."""
    import json

    college_options = list(active_colleges_queryset().values_list('name', flat=True))
    course_map = courses_by_college()
    year_level_map = year_levels_by_college()
    optional_map = course_optional_by_college()
    course_options = sorted({name for names in course_map.values() for name in names})

    return {
        'college_options': college_options,
        'course_options': course_options,
        'college_options_json': json.dumps(college_options),
        'course_options_by_college_json': json.dumps(course_map),
        'year_level_options_by_college_json': json.dumps(year_level_map),
        'course_optional_by_college_json': json.dumps(optional_map),
    }
