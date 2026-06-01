"""Admin settings views for college / course / year-level catalog."""

from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .academic_catalog import college_catalog_counts
from .academic_forms import CollegeDepartmentForm, CourseProgramForm, YearLevelOptionForm
from .decorators import admin_required
from .models import CollegeDepartment, CourseProgram, YearLevelOption


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

    if request.method == 'POST' and 'toggle_id' in request.POST:
        college = get_object_or_404(CollegeDepartment, pk=request.POST['toggle_id'])
        if college.is_active:
            has_active_children = (
                college.course_programs.filter(is_active=True).exists()
                or college.year_levels.filter(is_active=True).exists()
            )
            if has_active_children and request.POST.get('confirm_cascade') != '1':
                messages.warning(
                    request,
                    f'"{college.name}" has active courses or year levels. '
                    'Confirm deactivation to deactivate the college and its catalog items.',
                )
            else:
                college.is_active = False
                college.save(update_fields=['is_active', 'updated_at'])
                if has_active_children:
                    college.course_programs.filter(is_active=True).update(is_active=False)
                    college.year_levels.filter(is_active=True).update(is_active=False)
                messages.success(request, f'"{college.name}" deactivated.')
        else:
            college.is_active = True
            college.save(update_fields=['is_active', 'updated_at'])
            messages.success(request, f'"{college.name}" reactivated.')
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
        if request.POST.get('action') == 'cascade_deactivate':
            college.is_active = False
            college.save(update_fields=['is_active', 'updated_at'])
            college.course_programs.filter(is_active=True).update(is_active=False)
            college.year_levels.filter(is_active=True).update(is_active=False)
            messages.success(request, f'"{college.name}" and its active catalog items were deactivated.')
            return redirect('core:settings_colleges')

        form = CollegeDepartmentForm(request.POST, instance=college)
        if form.is_valid():
            updated = form.save()
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
        if request.POST.get('action') == 'toggle' and request.POST.get('course_id'):
            course = get_object_or_404(CourseProgram, pk=request.POST['course_id'], college_department=college)
            course.is_active = not course.is_active
            course.save(update_fields=['is_active', 'updated_at'])
            state = 'activated' if course.is_active else 'deactivated'
            messages.success(request, f'"{course.name}" {state}.')
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
        if request.POST.get('action') == 'toggle' and request.POST.get('year_level_id'):
            level = get_object_or_404(YearLevelOption, pk=request.POST['year_level_id'], college_department=college)
            level.is_active = not level.is_active
            level.save(update_fields=['is_active', 'updated_at'])
            state = 'activated' if level.is_active else 'deactivated'
            messages.success(request, f'"{level.name}" {state}.')
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
