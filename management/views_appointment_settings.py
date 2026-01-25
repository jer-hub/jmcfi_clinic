from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from core.decorators import admin_required
from .models import AppointmentTypeDefault, Appointment
from .forms_appointment_defaults import AppointmentTypeDefaultForm
from django.contrib.auth import get_user_model

User = get_user_model()


@login_required
@admin_required
def appointment_type_settings(request):
    """
    View for admin to manage default in-charge doctors for each appointment type.
    Displays all appointment types and their current defaults.
    """
    # Get all appointment type choices
    appointment_types = dict(Appointment.APPOINTMENT_TYPE_CHOICES)
    
    # Get existing defaults
    existing_defaults = AppointmentTypeDefault.objects.select_related('default_doctor').all()
    existing_types = {d.appointment_type: d for d in existing_defaults}
    
    # Create a comprehensive list with all types
    defaults_list = []
    for type_key, type_label in appointment_types.items():
        if type_key in existing_types:
            defaults_list.append(existing_types[type_key])
        else:
            # Create a placeholder for types without defaults
            defaults_list.append({
                'appointment_type': type_key,
                'type_display': type_label,
                'default_doctor': None,
                'is_active': False,
                'is_placeholder': True
            })
    
    context = {
        'defaults_list': defaults_list,
        'appointment_types': appointment_types,
    }
    
    return render(request, 'management/appointment_settings/appointment_type_settings.html', context)


@login_required
@admin_required
def edit_appointment_type_default(request, type_key=None):
    """
    View for admin to edit or create a default in-charge for an appointment type.
    """
    # Try to get existing default or create new
    if type_key:
        appointment_default = AppointmentTypeDefault.objects.filter(appointment_type=type_key).first()
    else:
        appointment_default = None
    
    if request.method == 'POST':
        form = AppointmentTypeDefaultForm(request.POST, instance=appointment_default)
        if form.is_valid():
            default = form.save(commit=False)
            default.updated_by = request.user
            default.save()
            
            type_display = default.get_appointment_type_display()
            doctor_name = f"Dr. {default.default_doctor.get_full_name()}" if default.default_doctor else "None"
            
            messages.success(
                request,
                f'Successfully updated default in-charge for {type_display} to {doctor_name}.'
            )
            return redirect('management:appointment_type_settings')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        # Pre-fill appointment type if creating new
        initial_data = {}
        if type_key and not appointment_default:
            initial_data['appointment_type'] = type_key
            initial_data['is_active'] = True
        
        form = AppointmentTypeDefaultForm(instance=appointment_default, initial=initial_data)
    
    context = {
        'form': form,
        'appointment_default': appointment_default,
        'type_key': type_key,
        'is_edit': appointment_default is not None,
    }
    
    return render(request, 'management/appointment_settings/edit_appointment_type_default.html', context)


@login_required
@admin_required
def toggle_appointment_type_default(request, default_id):
    """
    Quick toggle for activating/deactivating an appointment type default.
    """
    if request.method == 'POST':
        default = get_object_or_404(AppointmentTypeDefault, id=default_id)
        default.is_active = not default.is_active
        default.updated_by = request.user
        default.save()
        
        status = "activated" if default.is_active else "deactivated"
        messages.success(
            request,
            f'Default for {default.get_appointment_type_display()} has been {status}.'
        )
    
    return redirect('management:appointment_type_settings')


@login_required
@admin_required
def delete_appointment_type_default(request, default_id):
    """
    Delete an appointment type default.
    """
    if request.method == 'POST':
        default = get_object_or_404(AppointmentTypeDefault, id=default_id)
        type_display = default.get_appointment_type_display()
        default.delete()
        
        messages.success(
            request,
            f'Default in-charge for {type_display} has been removed.'
        )
    
    return redirect('management:appointment_type_settings')
