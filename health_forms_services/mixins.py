"""
Mixins for Django views - handles common patterns in health forms app
"""

from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q


class FormAccessMixin:
    """
    Mixin to handle role-based form access control.
    - Staff/doctors: Can see all forms
    - Students: Can see only their own forms
    - Auto-filters queryset based on user role
    """
    model = None  # Must be set by subclass (e.g., HealthProfileForm)
    
    def get_queryset(self):
        """Filter queryset based on user role"""
        qs = super().get_queryset()
        user = self.request.user
        
        # Prefetch common relations to avoid N+1 queries
        qs = qs.select_related('user', 'reviewed_by')
        
        # Staff/doctors can see all forms; students see only their own
        if user.role == 'student':
            qs = qs.filter(user=user)
        
        return qs
    
    def get_object(self, queryset=None):
        """Get object with role-based access check"""
        obj = super().get_object(queryset)
        user = self.request.user
        
        # Additional check: students can only view their own forms
        if user.role == 'student' and obj.user != user:
            raise PermissionDenied("You don't have permission to access this form.")
        
        return obj


class RoleRequiredMixin:
    """
    Mixin to restrict view access to specific user roles.
    Set allowed_roles class attribute (e.g., allowed_roles = ['staff', 'doctor', 'admin'])
    """
    allowed_roles = []
    
    def dispatch(self, request, *args, **kwargs):
        """Check if user has allowed role"""
        if not request.user.is_authenticated:
            return redirect('login')
        
        if request.user.role not in self.allowed_roles:
            messages.error(request, f'Permission denied. Required roles: {", ".join(self.allowed_roles)}')
            raise PermissionDenied(f'User role "{request.user.role}" not in allowed roles: {self.allowed_roles}')
        
        return super().dispatch(request, *args, **kwargs)


class FormListSearchMixin:
    """
    Mixin to add search and filtering capabilities to form list views.
    -apply_filters() method processes search queries and status filters
    """
    search_fields = ['last_name', 'first_name', 'user__email']  # Override in subclass
    filterable_fields = {'status': 'status'}  # Override in subclass
    
    def get_queryset(self):
        """Apply search and filters to queryset"""
        qs = super().get_queryset()
        
        # Search
        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            search_filter = Q()
            for field in self.search_fields:
                search_filter |= Q(**{f'{field}__icontains': search_query})
            qs = qs.filter(search_filter)
        
        # Filters
        for param, field in self.filterable_fields.items():
            value = self.request.GET.get(param, '').strip()
            if value:
                qs = qs.filter(**{field: value})
        
        return qs
    
    def get_context_data(self, **kwargs):
        """Add search and filter values to context"""
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        context['status_filter'] = self.request.GET.get('status', '')
        return context


class FormStatusWorkflowMixin:
    """
    Mixin to handle form status workflow (PENDING -> COMPLETED/REJECTED).
    Provides common methods for status transitions.
    """
    
    def can_review_form(self):
        """Check if user can review forms"""
        return self.request.user.role in ['staff', 'doctor', 'admin']
    
    def can_delete_form(self, form_obj):
        """Check if form can be deleted (only pending/rejected)"""
        allowed_statuses = ['pending', 'rejected']
        return form_obj.status in allowed_statuses
    
    def can_edit_form(self, form_obj):
        """Check if form can be edited"""
        # Generally allow editing of pending/rejected forms
        return form_obj.status in ['pending', 'rejected']
    
    def mark_as_reviewed(self, form_obj, decision, notes=''):
        """
        Mark form as reviewed (COMPLETED or REJECTED)
        
        Args:
            form_obj: The form instance
            decision: 'completed' or 'rejected'
            notes: Optional review notes
        """
        from django.utils import timezone
        
        if not self.can_review_form():
            raise PermissionDenied("You don't have permission to review forms.")
        
        if decision not in ['completed', 'rejected']:
            raise ValueError(f"Invalid decision: {decision}. Must be 'completed' or 'rejected'.")
        
        form_obj.status = decision
        form_obj.reviewed_by = self.request.user
        form_obj.reviewed_at = timezone.now()
        if notes:
            form_obj.review_notes = notes
        form_obj.save()
        
        return form_obj


class PaginationMixin:
    """
    Mixin to handle pagination with default per-page setting.
    Override paginate_by in subclass to change page size.
    """
    paginate_by = 10
    
    def get_paginate_by(self, queryset):
        """Allow dynamic page size via URL parameter"""
        per_page = self.request.GET.get('per_page', self.paginate_by)
        try:
            return max(1, int(per_page))  # Min 1, prevent zero or negative
        except (TypeError, ValueError):
            return self.paginate_by
