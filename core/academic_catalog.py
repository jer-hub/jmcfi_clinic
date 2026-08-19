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


def validate_academic_affiliation(
    *,
    is_employee,
    department,
    course,
    year_level,
    add_error,
    department_field='department',
    course_field='course',
    year_level_field='year_level',
    others_mode=False,
):
    """Validate college/department/course/year like patient profile profiling."""
    department = (department or '').strip()
    course = (course or '').strip()
    year_level = (year_level or '').strip()

    if not others_mode and department:
        others_mode = not CollegeDepartment.objects.filter(
            is_active=True, name=department
        ).exists()

    if is_employee:
        if not department:
            add_error(
                department_field,
                'Department is required for employees.',
            )
            return
        if not others_mode and not CollegeDepartment.objects.filter(is_active=True, name=department).exists():
            add_error(department_field, 'Select a valid College/Department.')
        return

    if not department:
        return

    if others_mode:
        return

    if not CollegeDepartment.objects.filter(is_active=True, name=department).exists():
        add_error(department_field, 'Select a valid College/Department.')
        return

    course_is_optional = is_course_optional_for_department(department)
    if not course and not course_is_optional:
        add_error(
            course_field,
            'Course/Program is required for the selected College/Department.',
        )

    if course and not CourseProgram.objects.filter(
        is_active=True,
        college_department__name=department,
        name=course,
    ).exists():
        add_error(
            course_field,
            'Course/Program must match the selected College/Department.',
        )

    if year_level and not YearLevelOption.objects.filter(
        is_active=True,
        college_department__name=department,
        name=year_level,
    ).exists():
        add_error(
            year_level_field,
            'Year Level must match the selected College/Department.',
        )


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


def _patient_user_id_from_instance(instance):
    """Resolve linked patient user id from common clinic model shapes."""
    if instance is None:
        return None
    user_id = getattr(instance, 'user_id', None)
    if user_id:
        return user_id
    user = getattr(instance, 'user', None)
    user_id = getattr(user, 'pk', None)
    if user_id:
        return user_id
    # DentalRecord and similar: patient FK → User
    patient = getattr(instance, 'patient', None)
    return getattr(patient, 'pk', None)


def soft_fill_academic_fields_from_patient_profile(instance) -> None:
    """
    Copy blank academic fields from the linked PatientProfile onto *instance*
    (in memory only). Call before ModelForm.__init__ so model_to_dict picks them up.

    Supports ``department_college_office``, ``department``, ``institution_id``,
    ``course``, and ``year_level`` when present on the model.
    """
    user_id = _patient_user_id_from_instance(instance)
    if not user_id:
        return

    # Always query — avoid stale reverse-OneToOne cache on user.patient_profile.
    profile = PatientProfile.objects.filter(user_id=user_id).first()
    if profile is None:
        return

    is_employee = bool(getattr(profile, 'is_employee', False))
    department = getattr(profile, 'department', '') or ''
    fallbacks = {
        'department_college_office': department,
        'department': department,
        'institution_id': getattr(profile, 'patient_id', '') or '',
    }
    if not is_employee:
        fallbacks['course'] = getattr(profile, 'course', '') or ''
        fallbacks['year_level'] = getattr(profile, 'year_level', '') or ''

    for field_name, raw in fallbacks.items():
        if not hasattr(instance, field_name):
            continue
        if str(getattr(instance, field_name, None) or '').strip():
            continue
        value = str(raw or '').strip()
        if value:
            setattr(instance, field_name, value)
