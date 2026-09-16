"""User management views (admin only)."""

from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from core.decorators import admin_required
from core.forms import (
    PasswordResetForm,
    UserChangeRoleForm,
    UserCreationForm,
    UserEditForm,
)
from core.htmx_utils import htmx_add_toast, htmx_add_trigger, htmx_redirect, is_htmx_request
from core.models import AccountProvisioningAudit
from core.notification_delivery import notify_user
from core.profile_forms import (
    get_or_create_profile,
    instantiate_profile_form,
    patient_catalog_context_for_form,
    swap_profile_for_role_change,
)
from core.roles import ROLE_PATIENT, role_matches
from core.user_management_services import (
    build_active_user_list_context,
    get_user_detail_summary,
    get_user_management_stats,
    soft_delete_user,
    toggle_user_status,
)
from core.views.helpers import _create_user_invite, _log_provisioning_action

User = get_user_model()


@login_required
@admin_required
def user_stats_cards(request):
    """HTMX partial: return just the stats cards for dynamic refresh."""
    stats = get_user_management_stats()
    return render(request, 'core/user_management/_user_stats_cards.html', {'stats': stats})


@login_required
@admin_required
def user_management(request):
    """List all users with filtering and search"""
    status_filter = request.GET.get('status', '')
    if status_filter == 'deleted':
        role_filter = request.GET.get('role', '')
        search_query = request.GET.get('search', '')
        query_string = urlencode({k: v for k, v in {'role': role_filter, 'search': search_query}.items() if v})
        target = reverse('core:deleted_user_management')
        return redirect(f'{target}?{query_string}' if query_string else target)

    context = build_active_user_list_context(request)

    if is_htmx_request(request):
        return render(request, 'core/user_management/_user_table_body.html', context)

    return render(request, 'core/user_management/user_list.html', context)


@login_required
@admin_required
def user_detail(request, user_id):
    """View detailed information about a specific user"""
    user = get_object_or_404(User, id=user_id)
    profile, stats, recent_activity = get_user_detail_summary(user)
    
    context = {
        'viewed_user': user,
        'profile': profile,
        'stats': stats,
        'recent_activity': recent_activity,
    }
    
    return render(request, 'core/user_management/user_detail.html', context)


@login_required
@admin_required
def user_create(request):
    """Create a new user"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save()
                invite_link = ''
                if user.onboarding_status == User.ONBOARDING_STATUS.PENDING_ACTIVATION:
                    _invite, raw_token = _create_user_invite(user=user, created_by=request.user)
                    invite_link = request.build_absolute_uri(
                        reverse('core:accept_invite', kwargs={'token': raw_token})
                    )

                create_action = (
                    AccountProvisioningAudit.ACTION.CREATED_PENDING
                    if user.onboarding_status == User.ONBOARDING_STATUS.PENDING_ACTIVATION
                    else AccountProvisioningAudit.ACTION.CREATED_ACTIVE
                )
                _log_provisioning_action(
                    request=request,
                    actor=request.user,
                    target_user=user,
                    action=create_action,
                    metadata={
                        'onboarding_status': user.onboarding_status,
                        'is_active': user.is_active,
                    },
                )

                # Create notification for the new user
                is_pending_activation = user.onboarding_status == User.ONBOARDING_STATUS.PENDING_ACTIVATION
                notify_user(
                    user=user,
                    title='Welcome to JMCFI Clinic',
                    message=(
                        'Your account has been created. Use your invitation link to activate your account.'
                        if is_pending_activation
                        else 'Your account has been created. Please complete your profile to get started.'
                    ),
                    notification_type='general'
                )

            if user.onboarding_status == User.ONBOARDING_STATUS.PENDING_ACTIVATION:
                messages.success(request, 'User created in pending activation state.')
                if invite_link:
                    messages.info(request, f'Invite link: {invite_link}')
            else:
                messages.success(request, 'User created and activated successfully!')
            return redirect('core:user_detail', user_id=user.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserCreationForm()
    
    context = {
        'form': form,
        'action': 'Create',
    }
    
    return render(request, 'core/user_management/user_form.html', context)


def _lock_user_edit_form_for_admin_target(form, is_admin_user):
    if is_admin_user:
        form.fields['is_active'].disabled = True


def _user_edit_context(viewed_user, user_form, profile_form, profile, is_admin_user):
    context = {
        'user_form': user_form,
        'form': profile_form,
        'viewed_user': viewed_user,
        'profile': profile,
        'is_admin_user': is_admin_user,
        'include_academic_catalog': role_matches(viewed_user.role, ROLE_PATIENT),
    }
    if role_matches(viewed_user.role, ROLE_PATIENT):
        context.update(patient_catalog_context_for_form(profile_form, viewed_user))
    return context


@login_required
@admin_required
def user_edit(request, user_id):
    """Edit an existing user (account + full profile)."""
    user = get_object_or_404(User, id=user_id)
    is_admin_user = user.role == 'admin'

    try:
        profile = get_or_create_profile(user)
    except ValueError:
        messages.error(request, f'Profile editing not available for role {user.role!r}.')
        return redirect('core:user_detail', user_id=user.id)

    if request.method == 'POST':
        user_form = UserEditForm(request.POST, instance=user)
        _lock_user_edit_form_for_admin_target(user_form, is_admin_user)
        profile_form = instantiate_profile_form(
            user, profile=profile, data=request.POST, files=request.FILES, editor=request.user,
        )

        if user_form.is_valid() and profile_form.is_valid():
            with transaction.atomic():
                user = user_form.save()
                profile = profile_form.save(commit=False)
                profile.user = user
                profile.save()
            messages.success(request, 'User updated successfully!')
            return redirect('core:user_detail', user_id=user.id)

        messages.error(request, 'Please correct the errors below.')
    else:
        user_form = UserEditForm(instance=user)
        _lock_user_edit_form_for_admin_target(user_form, is_admin_user)
        profile_form = instantiate_profile_form(user, profile=profile, editor=request.user)

    context = _user_edit_context(user, user_form, profile_form, profile, is_admin_user)
    return render(request, 'core/user_management/user_edit.html', context)


@login_required
@admin_required
def user_change_role(request, user_id):
    """Change a user's role via modal (HTMX) or POST fallback."""
    user = get_object_or_404(User, id=user_id)
    modal_template = 'core/user_management/_user_change_role_modal.html'

    def _htmx_error_toast(message, *, status=400, form=None):
        context = {'viewed_user': user}
        if form is not None:
            context['form'] = form
        else:
            context['form'] = UserChangeRoleForm(user=user)
        response = render(request, modal_template, context, status=status)
        return htmx_add_toast(response, message, 'error')

    if user.role == 'admin':
        message = 'Cannot change admin user roles.'
        if is_htmx_request(request):
            return _htmx_error_toast(message)
        messages.error(request, message)
        return redirect('core:user_detail', user_id=user.id)

    if user.id == request.user.id:
        message = 'Cannot change your own role.'
        if is_htmx_request(request):
            return _htmx_error_toast(message)
        messages.error(request, message)
        return redirect('core:user_detail', user_id=user.id)

    if request.method == 'POST':
        form = UserChangeRoleForm(request.POST, user=user)
        if form.is_valid():
            old_role = user.role
            new_role = form.cleaned_data['role']
            with transaction.atomic():
                user.role = new_role
                user.save(update_fields=['role'])
                swap_profile_for_role_change(user, old_role)
                # Clinical module grants: clear when entering/leaving doctor or staff.
                user.__dict__.pop('staff_profile', None)
                if new_role in ('doctor', 'staff') or old_role in ('doctor', 'staff'):
                    try:
                        staff_profile = user.staff_profile
                    except Exception:
                        staff_profile = None
                    if staff_profile is not None and staff_profile.allowed_clinical_modules:
                        staff_profile.allowed_clinical_modules = []
                        staff_profile.save(update_fields=['allowed_clinical_modules'])
                _log_provisioning_action(
                    request,
                    request.user,
                    user,
                    AccountProvisioningAudit.ACTION.ROLE_CHANGED,
                    metadata={'from': old_role, 'to': new_role},
                )
            for key in (
                f'profile_complete_{user.id}_{old_role}',
                f'profile_complete_{user.id}_{new_role}',
                f'profile_complete_{user.id}',
            ):
                if key in request.session:
                    del request.session[key]

            status_message = f'Role changed from {old_role} to {new_role}.'

            if is_htmx_request(request):
                from django.template.loader import render_to_string

                # Clear relation caches so detail summary sees the new profile model.
                user.__dict__.pop('patient_profile', None)
                user.__dict__.pop('staff_profile', None)
                user._state.fields_cache.pop('patient_profile', None)
                user._state.fields_cache.pop('staff_profile', None)
                user.refresh_from_db()

                profile, stats, recent_activity = get_user_detail_summary(user)
                card_html = render_to_string(
                    'core/user_management/partials/_user_detail_card.html',
                    {
                        'viewed_user': user,
                        'profile': profile,
                        'stats': stats,
                        'recent_activity': recent_activity,
                    },
                    request=request,
                )
                # Main swap clears modal body; OOB refreshes the detail card in place.
                response = HttpResponse(
                    '<div id="user-change-role-modal-body"></div>'
                    + card_html.replace(
                        'id="user-detail-card"',
                        'id="user-detail-card" hx-swap-oob="outerHTML"',
                        1,
                    )
                )
                response = htmx_add_toast(response, status_message, 'success')
                # Refresh list + stats when change-role was opened from user management.
                response = htmx_add_trigger(response, 'refreshUserTable')
                response = htmx_add_trigger(response, 'refreshUserStats')
                return response

            messages.success(request, status_message)
            return redirect('core:user_detail', user_id=user.id)

        error_message = (
            form.non_field_errors()[0]
            if form.non_field_errors()
            else 'Could not change role. Please try again.'
        )
        if is_htmx_request(request):
            return _htmx_error_toast(error_message, form=form)
        messages.error(request, error_message)
        return redirect('core:user_detail', user_id=user.id)

    if is_htmx_request(request):
        form = UserChangeRoleForm(user=user)
        return render(request, modal_template, {'form': form, 'viewed_user': user})

    return redirect('core:user_detail', user_id=user.id)


@login_required
@admin_required
def user_delete(request, user_id):
    """Soft-delete a user using the shared modal confirmation flow."""
    user = get_object_or_404(User, id=user_id)
    modal_template = 'core/user_management/_user_delete_modal.html'

    if user.role == 'admin':
        messages.error(request, 'Cannot delete admin users.')
        if is_htmx_request(request):
            return htmx_redirect(reverse('core:user_detail', kwargs={'user_id': user.id}))
        return redirect('core:user_detail', user_id=user.id)

    if user.id == request.user.id:
        messages.error(request, 'Cannot delete your own account.')
        if is_htmx_request(request):
            return htmx_redirect(reverse('core:user_detail', kwargs={'user_id': user.id}))
        return redirect('core:user_detail', user_id=user.id)

    if request.method == 'POST':
        soft_delete_user(request=request, actor=request.user, target_user=user)
        notify_user(
            user=user,
            title='Account Deleted',
            message='Your account has been soft-deleted by an administrator. Please contact an administrator if you need to restore access.',
            notification_type='general',
        )
        messages.success(request, 'User has been soft-deleted.')
        if is_htmx_request(request):
            return htmx_redirect(reverse('core:user_management'))
        return redirect('core:user_management')

    if is_htmx_request(request):
        return render(request, modal_template, {'viewed_user': user})

    return redirect('core:user_detail', user_id=user.id)


@login_required
@admin_required
@require_http_methods(["POST"])
def user_toggle_status(request, user_id):
    """Toggle user active/inactive status"""
    user = get_object_or_404(User, id=user_id)

    if user.role == 'admin':
        messages.error(request, 'Cannot deactivate admin users.')
        if is_htmx_request(request):
            response = render(request, 'partials/messages.html')
            return htmx_add_toast(response, 'Cannot deactivate admin users.', 'error')
        return redirect('core:user_detail', user_id=user.id)

    if user.id == request.user.id:
        messages.error(request, 'Cannot deactivate your own account.')
        if is_htmx_request(request):
            response = render(request, 'partials/messages.html')
            return htmx_add_toast(response, 'Cannot deactivate your own account.', 'error')
        return redirect('core:user_detail', user_id=user.id)
    
    toggle_user_status(request=request, actor=request.user, target_user=user)

    from django.template.loader import render_to_string
    status_html = render_to_string(
        'core/user_management/_user_status_badge.html',
        {'badge_user': user},
        request=request,
    )

    status_message = (
        'Account activated successfully.' if user.is_active
        else 'Account deactivated successfully.'
    )
    messages.success(request, status_message)

    notify_user(
        user=user,
        title='Account Activated' if user.is_active else 'Account Deactivated',
        message=(
            'Your account has been activated by an administrator.'
            if user.is_active
            else 'Your account has been deactivated. Please contact an administrator for more information.'
        ),
        notification_type='general',
    )

    if is_htmx_request(request):
        response = render(request, 'partials/messages.html')
        response = htmx_add_trigger(
            response,
            'updateStatus',
            {'id': str(user.id), 'html': status_html},
        )
        response = htmx_add_trigger(response, 'refreshUserStats')
        return htmx_add_toast(response, status_message)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        messages.get_messages(request).used = True
        return JsonResponse({
            'status': 'success',
            'is_active': user.is_active,
            'message': status_message,
        })

    return redirect('core:user_detail', user_id=user.id)


@login_required
@admin_required
@require_http_methods(["POST"])
def user_resend_invite(request, user_id):
    """Generate a new invite link for a pending user account."""
    user = get_object_or_404(User, id=user_id)

    if user.role == 'admin':
        messages.error(request, 'Cannot manage invites for admin users.')
        return redirect('core:user_detail', user_id=user.id)

    if user.onboarding_status != User.ONBOARDING_STATUS.PENDING_ACTIVATION:
        messages.error(request, 'Invite can only be regenerated for pending activation users.')
        return redirect('core:user_detail', user_id=user.id)

    _invite, raw_token = _create_user_invite(user=user, created_by=request.user)
    invite_link = request.build_absolute_uri(
        reverse('core:accept_invite', kwargs={'token': raw_token})
    )

    notify_user(
        user=user,
        title='New Invitation Link',
        message='A new account invitation link has been generated for you by an administrator.',
        notification_type='general'
    )

    messages.success(request, 'New invite link generated.')
    messages.info(request, f'Invite link: {invite_link}')
    return redirect('core:user_detail', user_id=user.id)


@login_required
@admin_required
def user_reset_password(request, user_id):
    """Reset user password"""
    user = get_object_or_404(User, id=user_id)
    
    # Prevent resetting admin passwords
    if user.role == 'admin':
        messages.error(request, 'Cannot reset admin user passwords.')
        return redirect('core:user_detail', user_id=user.id)
    
    if request.method == 'POST':
        form = PasswordResetForm(request.POST, user=user)
        if form.is_valid():
            new_password = form.cleaned_data['new_password1']
            user.set_password(new_password)
            user.save()
            
            # Create notification for the user
            notify_user(
                user=user,
                title='Password Reset',
                message='Your password has been reset by an administrator. Please login with your new password.',
                notification_type='general'
            )
            
            messages.success(request, 'Password has been reset successfully.')
            return redirect('core:user_detail', user_id=user.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PasswordResetForm(user=user)
    
    context = {
        'form': form,
        'viewed_user': user,
    }
    
    return render(request, 'core/user_management/user_reset_password.html', context)
