"""
Bulk action views for health forms.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from core.decorators import role_required

from ..models import HealthProfileForm


@method_decorator(login_required, name='dispatch')
@method_decorator(role_required('staff', 'doctor', 'admin'), name='dispatch')
class HealthProfileBulkReviewView(View):
    """Bulk approve/reject for HealthProfileForms."""

    def post(self, request):
        form_ids = request.POST.get('form_ids', '')
        action = request.POST.get('action', '')

        if not form_ids or action not in ('completed', 'incomplete', 'rejected'):
            messages.error(request, 'Invalid bulk action.')
            return redirect('health_forms_services:forms_list')

        ids = [int(x) for x in form_ids.split(',') if x.strip().isdigit()]
        if not ids:
            messages.error(request, 'No forms selected.')
            return redirect('health_forms_services:forms_list')

        updated = HealthProfileForm.objects.filter(pk__in=ids).update(
            status=action,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )

        label_map = {'completed': 'approved', 'incomplete': 'marked incomplete', 'rejected': 'rejected'}
        label = label_map.get(action, action)
        messages.success(request, f'{updated} form(s) {label}.')
        return redirect('health_forms_services:forms_list')
