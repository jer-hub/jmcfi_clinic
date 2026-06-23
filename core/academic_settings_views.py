"""Admin settings views for college / course / year-level catalog."""

from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Exists, OuterRef
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse

from .academic_catalog import (
    CatalogDeleteError,
    college_catalog_counts,
    delete_college,
    delete_course,
    delete_year_level,
    patient_department_usage_count,
)
from .academic_forms import CollegeDepartmentForm, CourseProgramForm, YearLevelOptionForm
from .decorators import admin_required
from .htmx_utils import htmx_add_toast, is_htmx_request
from .models import CollegeDepartment, CourseProgram, SettingsChangeLog, YearLevelOption
from .settings_audit import log_boolean_toggle, log_form_field_changes, log_settings_change, scoped_field_name


def _college_scope(college):
    return f'college: {college.name}'


def _course_scope(college, course):
    return f'course: {college.name} / {course.name}'


def _year_level_scope(college, year_level):
    return f'year level: {college.name} / {year_level.name}'


def _audit_academic(*, actor, scope, field_name, old_value='', new_value=''):
    log_settings_change(
        actor=actor,
        setting_type=SettingsChangeLog.SettingType.ACADEMIC,
        field_name=scoped_field_name(scope, field_name),
        old_value=old_value,
        new_value=new_value,
    )


def _audit_academic_delete(*, actor, scope, label):
    _audit_academic(
        actor=actor,
        scope=scope,
        field_name='deleted',
        old_value=label,
        new_value='',
    )


def _handle_catalog_delete_error(request, exc: CatalogDeleteError):
    messages.error(request, exc.message)


def _active_filter(queryset, active_param):
    if active_param == '0':
        return queryset.filter(is_active=False)
    if active_param == 'all':
        return queryset
    return queryset.filter(is_active=True)


def _redirect_settings_colleges(request):
    """Preserve list filters after POST (toggle) via hidden return_* fields."""
    params = {}
    return_q = (request.POST.get('return_q') or '').strip()
    return_active = request.POST.get('return_active')
    if return_q:
        params['q'] = return_q
    if return_active in ('all', '0', '1'):
        params['active'] = return_active
    url = reverse('core:settings_colleges')
    if params:
        url = f'{url}?{urlencode(params)}'
    return redirect(url)


def _annotate_college_catalog_children(queryset):
    active_courses = CourseProgram.objects.filter(
        college_department=OuterRef('pk'),
        is_active=True,
    )
    active_year_levels = YearLevelOption.objects.filter(
        college_department=OuterRef('pk'),
        is_active=True,
    )
    return queryset.annotate(
        has_active_courses=Exists(active_courses),
        has_active_year_levels=Exists(active_year_levels),
    )


def _college_with_counts(pk: int):
    return (
        _annotate_college_catalog_children(
            CollegeDepartment.objects.filter(pk=pk).annotate(
                course_count=Count('course_programs', distinct=True),
                year_level_count=Count('year_levels', distinct=True),
            )
        ).first()
    )


@login_required
@admin_required
def settings_academic_hub(request):
    counts = college_catalog_counts()
    return render(
        request,
        'core/settings/academic/hub.html',
        {
            'settings_subnav_active': 'academic',
            'counts': counts,
        },
    )


@login_required
@admin_required
def settings_colleges(request):
    active = request.GET.get('active', 'all')
    q = (request.GET.get('q') or '').strip()
    colleges = _active_filter(CollegeDepartment.objects.all(), active)
    if q:
        colleges = colleges.filter(name__icontains=q)
    colleges = _annotate_college_catalog_children(colleges.order_by('name'))
    colleges = colleges.annotate(
        course_count=Count('course_programs', distinct=True),
        year_level_count=Count('year_levels', distinct=True),
    )

    if request.method == 'POST' and request.POST.get('action') == 'delete' and request.POST.get('college_id'):
        college = get_object_or_404(CollegeDepartment, pk=request.POST['college_id'])
        scope = _college_scope(college)
        try:
            college_name, deleted_courses, deleted_levels = delete_college(college)
        except CatalogDeleteError as exc:
            _handle_catalog_delete_error(request, exc)
            return _redirect_settings_colleges(request)
        _audit_academic_delete(actor=request.user, scope=scope, label=college_name)
        if deleted_courses or deleted_levels:
            _audit_academic(
                actor=request.user,
                scope=scope,
                field_name='catalog_cascade',
                old_value=f'{deleted_courses} course(s), {deleted_levels} year level(s)',
                new_value='deleted',
            )
        messages.success(
            request,
            f'"{college_name}" and its catalog items were permanently deleted.',
        )
        return _redirect_settings_colleges(request)

    if request.method == 'POST' and 'toggle_id' in request.POST:
        college = get_object_or_404(CollegeDepartment, pk=request.POST['toggle_id'])
        toggle_message = ''
        toggle_toast_type = 'success'
        if college.is_active:
            has_active_children = (
                college.course_programs.filter(is_active=True).exists()
                or college.year_levels.filter(is_active=True).exists()
            )
            if has_active_children and request.POST.get('confirm_cascade') != '1':
                toggle_message = (
                    f'"{college.name}" has active courses or year levels. '
                    'Confirm deactivation to deactivate the college and its catalog items.'
                )
                toggle_toast_type = 'warning'
                messages.warning(
                    request,
                    toggle_message,
                )
            else:
                old_active = college.is_active
                college.is_active = False
                college.save(update_fields=['is_active', 'updated_at'])
                log_boolean_toggle(
                    actor=request.user,
                    setting_type=SettingsChangeLog.SettingType.ACADEMIC,
                    scope=_college_scope(college),
                    field_name='is_active',
                    old_value=old_active,
                    new_value=college.is_active,
                )
                if has_active_children:
                    college.course_programs.filter(is_active=True).update(is_active=False)
                    college.year_levels.filter(is_active=True).update(is_active=False)
                    _audit_academic(
                        actor=request.user,
                        scope=_college_scope(college),
                        field_name='catalog_cascade',
                        old_value='active',
                        new_value='deactivated (courses and year levels)',
                    )
                toggle_message = f'"{college.name}" deactivated.'
                messages.success(request, toggle_message)
        else:
            old_active = college.is_active
            college.is_active = True
            college.save(update_fields=['is_active', 'updated_at'])
            log_boolean_toggle(
                actor=request.user,
                setting_type=SettingsChangeLog.SettingType.ACADEMIC,
                scope=_college_scope(college),
                field_name='is_active',
                old_value=old_active,
                new_value=college.is_active,
            )
            toggle_message = f'"{college.name}" reactivated.'
            messages.success(request, toggle_message)
        if is_htmx_request(request):
            college_row = _college_with_counts(college.pk)
            html = render_to_string(
                'core/settings/academic/_college_row.html',
                {
                    'college': college_row,
                    'active_filter': active,
                    'search_q': q,
                },
                request=request,
            )
            response = HttpResponse(html)
            return htmx_add_toast(response, toggle_message, toggle_toast_type)
        return _redirect_settings_colleges(request)

    return render(
        request,
        'core/settings/academic/colleges_list.html',
        {
            'settings_subnav_active': 'academic',
            'colleges': colleges,
            'active_filter': active,
            'search_q': q,
        },
    )


@login_required
@admin_required
def settings_college_create(request):
    if request.method == 'POST':
        form = CollegeDepartmentForm(request.POST)
        if form.is_valid():
            college = form.save()
            log_form_field_changes(
                actor=request.user,
                setting_type=SettingsChangeLog.SettingType.ACADEMIC,
                form=form,
                scope=_college_scope(college),
            )
            messages.success(request, f'"{college.name}" created.')
            return redirect('core:settings_colleges')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = CollegeDepartmentForm(initial={'is_active': True})

    return render(
        request,
        'core/settings/academic/college_form.html',
        {
            'settings_subnav_active': 'academic',
            'form': form,
            'title': 'Add college / department',
            'submit_label': 'Create',
        },
    )


@login_required
@admin_required
def settings_college_edit(request, pk):
    college = get_object_or_404(CollegeDepartment, pk=pk)

    if request.method == 'POST':
        if request.POST.get('action') == 'delete':
            scope = _college_scope(college)
            try:
                college_name, deleted_courses, deleted_levels = delete_college(college)
            except CatalogDeleteError as exc:
                _handle_catalog_delete_error(request, exc)
                return redirect('core:settings_college_edit', pk=college.pk)
            _audit_academic_delete(actor=request.user, scope=scope, label=college_name)
            if deleted_courses or deleted_levels:
                _audit_academic(
                    actor=request.user,
                    scope=scope,
                    field_name='catalog_cascade',
                    old_value=f'{deleted_courses} course(s), {deleted_levels} year level(s)',
                    new_value='deleted',
                )
            messages.success(
                request,
                f'"{college_name}" and its catalog items were permanently deleted.',
            )
            return redirect('core:settings_colleges')

        if request.POST.get('action') == 'cascade_deactivate':
            old_active = college.is_active
            college.is_active = False
            college.save(update_fields=['is_active', 'updated_at'])
            college.course_programs.filter(is_active=True).update(is_active=False)
            college.year_levels.filter(is_active=True).update(is_active=False)
            log_boolean_toggle(
                actor=request.user,
                setting_type=SettingsChangeLog.SettingType.ACADEMIC,
                scope=_college_scope(college),
                field_name='is_active',
                old_value=old_active,
                new_value=college.is_active,
            )
            _audit_academic(
                actor=request.user,
                scope=_college_scope(college),
                field_name='catalog_cascade',
                old_value='active',
                new_value='deactivated (courses and year levels)',
            )
            messages.success(request, f'"{college.name}" and its active catalog items were deactivated.')
            return redirect('core:settings_colleges')

        form = CollegeDepartmentForm(request.POST, instance=college)
        if form.is_valid():
            updated = form.save()
            log_form_field_changes(
                actor=request.user,
                setting_type=SettingsChangeLog.SettingType.ACADEMIC,
                form=form,
                scope=_college_scope(updated),
            )
            messages.success(request, f'"{updated.name}" saved.')
            return redirect('core:settings_colleges')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = CollegeDepartmentForm(instance=college)

    active_courses = college.course_programs.filter(is_active=True).count()
    active_year_levels = college.year_levels.filter(is_active=True).count()

    return render(
        request,
        'core/settings/academic/college_form.html',
        {
            'settings_subnav_active': 'academic',
            'form': form,
            'college': college,
            'title': f'Edit {college.name}',
            'submit_label': 'Save changes',
            'active_courses': active_courses,
            'active_year_levels': active_year_levels,
            'total_courses': college.course_programs.count(),
            'total_year_levels': college.year_levels.count(),
            'patient_usage_count': patient_department_usage_count(college.name),
        },
    )


@login_required
@admin_required
def settings_college_courses(request, pk):
    college = get_object_or_404(CollegeDepartment, pk=pk)
    active = request.GET.get('active', 'all')
    courses = _active_filter(college.course_programs.all(), active).order_by('name')

    add_form = CourseProgramForm(college=college, initial={'is_active': True})
    edit_form = None
    edit_course = None

    edit_id = request.GET.get('edit')
    if edit_id and request.method == 'GET':
        edit_course = get_object_or_404(CourseProgram, pk=edit_id, college_department=college)
        edit_form = CourseProgramForm(instance=edit_course, college=college)

    if request.method == 'POST':
        if request.POST.get('action') == 'delete' and request.POST.get('course_id'):
            course = get_object_or_404(CourseProgram, pk=request.POST['course_id'], college_department=college)
            scope = _course_scope(college, course)
            course_name = course.name
            try:
                delete_course(course)
            except CatalogDeleteError as exc:
                _handle_catalog_delete_error(request, exc)
                return redirect('core:settings_college_courses', pk=college.pk)
            _audit_academic_delete(actor=request.user, scope=scope, label=course_name)
            messages.success(request, f'"{course_name}" was permanently deleted.')
            return redirect('core:settings_college_courses', pk=college.pk)

        if request.POST.get('action') == 'toggle' and request.POST.get('course_id'):
            course = get_object_or_404(CourseProgram, pk=request.POST['course_id'], college_department=college)
            old_active = course.is_active
            course.is_active = not course.is_active
            course.save(update_fields=['is_active', 'updated_at'])
            log_boolean_toggle(
                actor=request.user,
                setting_type=SettingsChangeLog.SettingType.ACADEMIC,
                scope=_course_scope(college, course),
                field_name='is_active',
                old_value=old_active,
                new_value=course.is_active,
            )
            state = 'activated' if course.is_active else 'deactivated'
            toggle_message = f'"{course.name}" {state}.'
            messages.success(request, toggle_message)
            if is_htmx_request(request):
                html = render_to_string(
                    'core/settings/academic/_course_row.html',
                    {'course': course, 'college': college},
                    request=request,
                )
                response = HttpResponse(html)
                return htmx_add_toast(response, toggle_message)
            return redirect('core:settings_college_courses', pk=college.pk)

        course_id = request.POST.get('course_id')
        instance = None
        if course_id:
            instance = get_object_or_404(CourseProgram, pk=course_id, college_department=college)
        form = CourseProgramForm(request.POST, instance=instance, college=college)
        if form.is_valid():
            course = form.save(commit=False)
            course.college_department = college
            course.save()
            log_form_field_changes(
                actor=request.user,
                setting_type=SettingsChangeLog.SettingType.ACADEMIC,
                form=form,
                scope=_course_scope(college, course),
            )
            messages.success(request, f'"{course.name}" saved.')
            return redirect('core:settings_college_courses', pk=college.pk)
        messages.error(request, 'Please correct the errors below.')
        if instance:
            edit_course = instance
            edit_form = form
        else:
            add_form = form

    return render(
        request,
        'core/settings/academic/courses_list.html',
        {
            'settings_subnav_active': 'academic',
            'college': college,
            'courses': courses,
            'add_form': add_form,
            'edit_form': edit_form,
            'edit_course': edit_course,
            'active_filter': active,
        },
    )


@login_required
@admin_required
def settings_college_year_levels(request, pk):
    college = get_object_or_404(CollegeDepartment, pk=pk)
    active = request.GET.get('active', 'all')
    year_levels = _active_filter(college.year_levels.all(), active).order_by('sort_order', 'name')

    edit_level = None
    edit_form = None
    edit_id = request.GET.get('edit')
    if edit_id:
        edit_level = get_object_or_404(YearLevelOption, pk=edit_id, college_department=college)
        edit_form = YearLevelOptionForm(instance=edit_level, college=college)

    add_form = YearLevelOptionForm(college=college, initial={'is_active': True, 'sort_order': 0})

    if request.method == 'POST':
        if request.POST.get('action') == 'delete' and request.POST.get('year_level_id'):
            level = get_object_or_404(YearLevelOption, pk=request.POST['year_level_id'], college_department=college)
            scope = _year_level_scope(college, level)
            level_name = level.name
            try:
                delete_year_level(level)
            except CatalogDeleteError as exc:
                _handle_catalog_delete_error(request, exc)
                return redirect('core:settings_college_year_levels', pk=college.pk)
            _audit_academic_delete(actor=request.user, scope=scope, label=level_name)
            messages.success(request, f'"{level_name}" was permanently deleted.')
            return redirect('core:settings_college_year_levels', pk=college.pk)

        if request.POST.get('action') == 'toggle' and request.POST.get('year_level_id'):
            level = get_object_or_404(YearLevelOption, pk=request.POST['year_level_id'], college_department=college)
            old_active = level.is_active
            level.is_active = not level.is_active
            level.save(update_fields=['is_active', 'updated_at'])
            log_boolean_toggle(
                actor=request.user,
                setting_type=SettingsChangeLog.SettingType.ACADEMIC,
                scope=_year_level_scope(college, level),
                field_name='is_active',
                old_value=old_active,
                new_value=level.is_active,
            )
            state = 'activated' if level.is_active else 'deactivated'
            toggle_message = f'"{level.name}" {state}.'
            messages.success(request, toggle_message)
            if is_htmx_request(request):
                html = render_to_string(
                    'core/settings/academic/_year_level_row.html',
                    {'level': level, 'college': college},
                    request=request,
                )
                response = HttpResponse(html)
                return htmx_add_toast(response, toggle_message)
            return redirect('core:settings_college_year_levels', pk=college.pk)

        level_id = request.POST.get('year_level_id')
        instance = None
        if level_id:
            instance = get_object_or_404(YearLevelOption, pk=level_id, college_department=college)
        form = YearLevelOptionForm(request.POST, instance=instance, college=college)
        if form.is_valid():
            level = form.save(commit=False)
            level.college_department = college
            level.save()
            log_form_field_changes(
                actor=request.user,
                setting_type=SettingsChangeLog.SettingType.ACADEMIC,
                form=form,
                scope=_year_level_scope(college, level),
            )
            messages.success(request, f'"{level.name}" saved.')
            return redirect('core:settings_college_year_levels', pk=college.pk)
        messages.error(request, 'Please correct the errors below.')
        if instance:
            edit_level = instance
            edit_form = form
        else:
            add_form = form

    return render(
        request,
        'core/settings/academic/year_levels_list.html',
        {
            'settings_subnav_active': 'academic',
            'college': college,
            'year_levels': year_levels,
            'add_form': add_form,
            'edit_form': edit_form,
            'edit_level': edit_level,
            'active_filter': active,
        },
    )
