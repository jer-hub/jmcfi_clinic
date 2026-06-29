"""
Base class-based views for health forms services.

Shared foundation that all 5 form types inherit from:
- HealthProfileForm
- DentalHealthForm
- PatientChart
- Prescription
- DentalServicesRequest
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from core.decorators import role_required


# ---------------------------------------------------------------------------
# Decorators as method_decorator helpers
# ---------------------------------------------------------------------------

def staff_doctor_admin_required(view):
    """Class-compatible wrapper for @role_required('staff', 'doctor')."""
    return method_decorator(role_required('staff', 'doctor'), name='dispatch')(view)


# ---------------------------------------------------------------------------
# Base List View
# ---------------------------------------------------------------------------

class BaseFormListView(View):
    """Shared list view with search, status filter, pagination, role-filtered queryset.

    Subclasses set:
        model           – Django Model class
        template_name   – template path (extends _base_list.html)
        list_columns    – list of column keys (name_avatar, designation, status, date, actions)
        search_fields   – list of Q-compatible field lookups
        create_url_name – URL name for "create new" button
        form_type_label – human-readable label for the form type
        status_choices  – model's Status.choices (or override)
        per_page        – pagination page size (default 15)
    """

    model = None
    template_name = None
    list_columns = None
    search_fields = None
    create_url_name = None
    detail_url_name = None
    edit_url_name = None
    bulk_action_url_name = None
    form_type_label = None
    status_choices = None
    per_page = 15

    @method_decorator(login_required)
    @method_decorator(role_required('staff', 'doctor', 'admin'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        qs = self.model.objects.all()
        if hasattr(self.model, 'user'):
            qs = qs.select_related('user')
        if hasattr(self.model, 'reviewed_by'):
            qs = qs.select_related('reviewed_by')

        user = self.request.user
        from core.roles import is_patient_role
        if is_patient_role(user.role):
            qs = qs.filter(user=user)
        return qs

    def apply_filters(self, qs):
        search = self.request.GET.get('search', '')
        status_filter = self.request.GET.get('status', '')

        if search and self.search_fields:
            query = Q()
            for field in self.search_fields:
                query |= Q(**{f'{field}__icontains': search})
            qs = qs.filter(query)

        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs, search, status_filter

    def get(self, request):
        qs = self.get_queryset()
        qs, search, status_filter = self.apply_filters(qs)

        paginator = Paginator(qs, self.per_page)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)

        create_url = reverse(self.create_url_name) if self.create_url_name else None
        status_choices = self.status_choices or getattr(self.model, 'Status', None)
        if status_choices:
            status_choices = status_choices.choices

        ctx = {
            'forms': page_obj,
            'search': search,
            'status_filter': status_filter,
            'status_choices': status_choices,
            'create_url': create_url,
            'detail_url_name': self.detail_url_name,
            'edit_url_name': self.edit_url_name,
            'bulk_action_url_name': self.bulk_action_url_name,
            'list_columns': self.list_columns or [],
            'form_type_label': self.form_type_label or self.model._meta.verbose_name_plural,
            'total_count': qs.count() if hasattr(qs, 'count') else 0,
        }
        return render(request, self.template_name, ctx)


# ---------------------------------------------------------------------------
# Base Detail View
# ---------------------------------------------------------------------------

class BaseFormDetailView(View):
    """Shared detail view with role-checked access, status badge, action buttons.

    Subclasses set:
        model            – Django Model class
        template_name    – template path (extends _base_detail.html)
        detail_sections  – list of dicts: {key, label, icon, fields}
        list_url_name    – URL name for "back to list"
        edit_url_name    – URL name for edit view
        export_url_name  – URL name for JSON export
        docx_export_url_name – URL name for DOCX export
        form_context_key – context variable name for the form object (default 'form_obj')
    """

    model = None
    template_name = None
    detail_sections = None
    list_url_name = None
    edit_url_name = None
    export_url_name = None
    docx_export_url_name = None
    review_url_name = None
    delete_url_name = None
    form_context_key = 'form_obj'

    @method_decorator(login_required)
    @method_decorator(role_required('staff', 'doctor', 'admin'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_object(self):
        pk = self.kwargs.get('pk')
        qs = self.model.objects.all()
        if hasattr(self.model, 'user'):
            qs = qs.select_related('user')
        if hasattr(self.model, 'reviewed_by'):
            qs = qs.select_related('reviewed_by')

        user = self.request.user
        from core.roles import is_patient_role
        if is_patient_role(user.role):
            obj = get_object_or_404(qs, pk=pk, user=user)
        else:
            obj = get_object_or_404(qs, pk=pk)
        return obj

    def get_context_data(self, obj):
        user = self.request.user
        ctx = {
            self.form_context_key: obj,
            'can_edit': user.role in ['staff', 'doctor', 'admin'] or getattr(obj, 'user', None) == user,
            'can_review': user.role in ['staff', 'doctor', 'admin'],
            'can_delete': user.role in ['staff', 'doctor', 'admin'],
            'detail_sections': self.detail_sections or [],
            'list_url': reverse(self.list_url_name) if self.list_url_name else None,
            'edit_url': reverse(self.edit_url_name, kwargs={'pk': obj.pk}) if self.edit_url_name else None,
            'export_url': reverse(self.export_url_name, kwargs={'pk': obj.pk}) if self.export_url_name else None,
            'docx_export_url': reverse(self.docx_export_url_name, kwargs={'pk': obj.pk}) if self.docx_export_url_name else None,
            'review_url_name': self.review_url_name,
            'delete_url': reverse(self.delete_url_name, kwargs={'pk': obj.pk}) if self.delete_url_name else None,
            'form_type_label': getattr(self, 'form_type_label', None) or self.model._meta.verbose_name,
        }
        return ctx

    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        ctx = self.get_context_data(obj)
        return render(request, self.template_name, ctx)


# ---------------------------------------------------------------------------
# Base Edit View (tabbed sections)
# ---------------------------------------------------------------------------

class BaseFormEditView(View):
    """Shared tabbed edit view with section→form class mapping.

    Subclasses set:
        model            – Django Model class
        template_name    – template path (extends _base_edit.html)
        form_class_map   – dict: {section_key: FormClass}
        tabs             – list of dicts: {key, label, icon}
        detail_url_name  – URL name for back-to-detail link in template
        edit_url_name    – URL name to redirect after successful section save
        doctors_queryset – optional custom doctor queryset for assigning physician
    """

    model = None
    template_name = None
    form_class_map = None
    tabs = None
    field_groups = None  # {tab_key: [{label, fields}]} — optional section headers
    detail_url_name = None
    edit_url_name = None
    doctors_queryset = None
    personal_readonly = False

    def get_edit_context(self, obj, *, active_section, form_instances):
        return {
            'form_obj': obj,
            'forms': form_instances,
            'tabs': self.tabs or [],
            'field_groups': self.field_groups or {},
            'active_section': active_section,
            'doctors': self.get_doctors(),
            'detail_url': reverse(self.detail_url_name, kwargs={'pk': obj.pk}) if self.detail_url_name else None,
            'personal_readonly': getattr(self, 'personal_readonly', False),
            'edit_form_type': getattr(self, 'edit_form_type', ''),
        }

    @method_decorator(login_required)
    @method_decorator(role_required('staff', 'doctor', 'admin'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_object(self):
        pk = self.kwargs.get('pk')
        qs = self.model.objects.all()
        if hasattr(self.model, 'user'):
            qs = qs.select_related('user', 'reviewed_by')

        user = self.request.user
        from core.roles import is_patient_role
        if is_patient_role(user.role):
            return get_object_or_404(qs, pk=pk, user=user)
        return get_object_or_404(qs, pk=pk)

    def get_doctors(self):
        if self.doctors_queryset is not None:
            return self.doctors_queryset
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.filter(role__in=['doctor', 'staff']).order_by('first_name', 'last_name')

    def get_edit_redirect_url(self, obj, section):
        if self.edit_url_name:
            base = reverse(self.edit_url_name, kwargs={'pk': obj.pk})
            return f'{base}?section={section}'
        if self.detail_url_name:
            return reverse(self.detail_url_name, kwargs={'pk': obj.pk})
        return '/'

    def _build_form(self, form_class, *, instance, data=None):
        """Build a section form and pass request user when supported."""
        kwargs = {'instance': instance}
        if data is not None:
            kwargs['data'] = data
        try:
            return form_class(user=self.request.user, **kwargs)
        except TypeError:
            # Backward-compatible path for forms that do not accept `user`.
            return form_class(**kwargs)

    def get_extra_edit_context(self, obj):
        return {}

    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        form_instances = {}
        active_section = request.GET.get('section', (self.tabs[0]['key'] if self.tabs else 'personal'))

        for key, form_class in (self.form_class_map or {}).items():
            form_instances[key] = self._build_form(form_class, instance=obj)

        ctx = self.get_edit_context(obj, active_section=active_section, form_instances=form_instances)
        ctx.update(self.get_extra_edit_context(obj))
        return render(request, self.template_name, ctx)

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        section = request.POST.get('section', 'personal')
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        form_class = (self.form_class_map or {}).get(section)
        if not form_class:
            if is_ajax:
                return JsonResponse({'success': False, 'error': 'Invalid section.'}, status=400)
            messages.error(request, 'Invalid section.')
            return redirect(self.get_edit_redirect_url(obj, section))

        form = self._build_form(form_class, instance=obj, data=request.POST)
        if form.is_valid():
            saved_obj = form.save(commit=False)

            if hasattr(self, 'after_section_save'):
                self.after_section_save(saved_obj, section)

            saved_obj.save()

            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'section': section,
                    'message': f'{section.capitalize()} section saved.',
                    'timestamp': timezone.now().isoformat(),
                })
            messages.success(request, 'Form updated.')
            return redirect(self.get_edit_redirect_url(obj, section))

        if is_ajax:
            errors = {field: [str(error) for error in error_list] for field, error_list in form.errors.items()}
            return JsonResponse({'success': False, 'errors': errors}, status=400)

        form_instances = {}
        for key, form_class in (self.form_class_map or {}).items():
            if key == section:
                form_instances[key] = form
            else:
                form_instances[key] = self._build_form(form_class, instance=obj)

        ctx = self.get_edit_context(obj, active_section=section, form_instances=form_instances)
        ctx.update(self.get_extra_edit_context(obj))
        return render(request, self.template_name, ctx)
