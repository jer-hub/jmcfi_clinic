"""Inclusion tags that render ``components/sub_nav.html`` with per-app items."""

from django import template
from django.urls import reverse

from core.roles import ROLE_PATIENT, role_matches
from core.settings_service import get_role_features
from core.subnav_helpers import breadcrumb_subnav, enrich_subnav, is_active, nav_item, view_name
from core.utils import analytics_home_url_name

register = template.Library()


@register.simple_tag(takes_context=True)
def analytics_home_url(context):
    return reverse(analytics_home_url_name(context['request'].user))


def _patient_new_appointment_item(vn):
    return nav_item(
        'New Appointment',
        'appointments:schedule_appointment',
        icon='fa-plus',
        active=vn == 'appointments:schedule_appointment',
    )


def _append_patient_new_appointment(items, request):
    role = request.user.role
    if role_matches(role, ROLE_PATIENT) and get_role_features(role)['can_book_appointments']:
        items.append(_patient_new_appointment_item(view_name(request)))
    return items


@register.inclusion_tag('components/sub_nav.html', takes_context=True)
def appointments_subnav(context):
    request = context['request']
    vn = view_name(request)
    role = request.user.role
    items = [
        nav_item(
            'Appointments',
            'appointments:appointment_list',
            icon='fa-calendar-days',
            active=vn == 'appointments:appointment_list',
        ),
        nav_item(
            'Calendar',
            'appointments:appointment_calendar',
            icon='fa-calendar-days',
            active=vn == 'appointments:appointment_calendar',
        ),
    ]
    if role in ('doctor', 'staff'):
        items.append(
            nav_item(
                'Schedule for Patient',
                'appointments:schedule_for_patient',
                icon='fa-plus',
                active=vn == 'appointments:schedule_for_patient',
            )
        )
    _append_patient_new_appointment(items, request)
    return enrich_subnav(items, always_show_nav=True)


@register.inclusion_tag('components/sub_nav.html', takes_context=True)
def medical_records_subnav(context):
    vn = view_name(context['request'])
    role = context['request'].user.role
    items = [
        nav_item(
            'Medical Records',
            'medical_records:medical_records',
            icon='fa-file-medical',
            active=vn == 'medical_records:medical_records',
        ),
    ]
    if role in ('staff', 'doctor'):
        items.append(
            nav_item(
                'New Record',
                'medical_records:create_medical_record_for_patient',
                icon='fa-plus',
                active=is_active(
                    vn,
                    'medical_records:create_medical_record_for_patient',
                    'medical_records:create_medical_record',
                ),
            )
        )
    _append_patient_new_appointment(items, context['request'])
    return enrich_subnav(items, always_show_nav=True, nav_mb='mb-4')


@register.inclusion_tag('components/sub_nav.html', takes_context=True)
def dental_records_subnav(context):
    vn = view_name(context['request'])
    role = context['request'].user.role
    items = [
        nav_item(
            'Dental Records',
            'dental_records:dental_record_list',
            icon='fa-tooth',
            active=vn == 'dental_records:dental_record_list',
        ),
    ]
    if not role_matches(role, ROLE_PATIENT):
        items.append(
            nav_item(
                'New Record',
                'dental_records:dental_record_create',
                icon='fa-plus',
                active=vn == 'dental_records:dental_record_create',
            )
        )
    _append_patient_new_appointment(items, context['request'])
    return enrich_subnav(items, always_show_nav=True, nav_mb='mb-4')


def _document_requests_list_crumb():
    return {
        'label': 'Requests',
        'url': reverse('document_request:document_requests'),
        'icon': 'fa-file-medical',
    }


def _linked_request_detail_crumb(cert_id):
    from document_request.models import DocumentRequest

    linked = (
        DocumentRequest.objects.filter(medical_certificate_id=cert_id)
        .only('id')
        .first()
    )
    if not linked:
        return None
    return {
        'label': 'Request Details',
        'url': reverse('document_request:document_request_detail', args=[linked.id]),
    }


@register.inclusion_tag('components/sub_nav.html', takes_context=True)
def document_request_subnav(context):
    request = context['request']
    vn = view_name(request)

    if vn == 'document_request:document_request_detail':
        return breadcrumb_subnav(
            [
                _document_requests_list_crumb(),
                {'label': 'Request Details', 'icon': 'fa-file-lines'},
            ]
        )

    if vn == 'document_request:preview_medical_certificate':
        cert_id = request.resolver_match.kwargs.get('cert_id')
        crumbs = [_document_requests_list_crumb()]
        detail_crumb = _linked_request_detail_crumb(cert_id) if cert_id else None
        if detail_crumb:
            crumbs.append(detail_crumb)
        crumbs.append({'label': 'Certificate Preview', 'icon': 'fa-eye'})
        return breadcrumb_subnav(crumbs)

    items = [
        nav_item(
            'Requests',
            'document_request:document_requests',
            icon='fa-file-medical',
            active=is_active(
                vn,
                'document_request:document_requests',
                'document_request:process_document',
                'document_request:view_document',
            ),
        ),
    ]
    if role_matches(getattr(request.user, 'role', None), ROLE_PATIENT, 'doctor', 'staff', 'admin'):
        items.append(
            nav_item(
                'New Request',
                'document_request:request_document',
                icon='fa-plus',
                active=vn == 'document_request:request_document',
            )
        )
    if getattr(request.user, 'role', None) in ('doctor', 'staff', 'admin'):
        items.append(
            nav_item(
                'My Signature',
                'document_request:clinician_signature',
                icon='fa-signature',
                active=vn == 'document_request:clinician_signature',
            )
        )
    return enrich_subnav(items, always_show_nav=True, nav_mb='mb-4')


@register.inclusion_tag('components/sub_nav.html', takes_context=True)
def feedback_subnav(context):
    vn = view_name(context['request'])
    role = context['request'].user.role
    items = [
        nav_item(
            'Feedback',
            'feedback:feedback_list',
            icon='fa-comments',
            active=vn == 'feedback:feedback_list',
        ),
        nav_item(
            'Submit',
            'feedback:submit_feedback',
            icon='fa-pen',
            active=is_active(vn, 'feedback:submit_feedback', 'feedback:submit_feedback_appointment'),
        ),
    ]
    if role in ('admin', 'staff', 'doctor'):
        items.append(
            nav_item(
                'Statistics',
                'feedback:feedback_stats',
                icon='fa-chart-pie',
                active=vn == 'feedback:feedback_stats',
            )
        )
    return enrich_subnav(items)


@register.inclusion_tag('components/sub_nav.html', takes_context=True)
def health_tips_subnav(context):
    vn = view_name(context['request'])
    role = context['request'].user.role
    items = [
        nav_item(
            'Health Tips',
            'health_tips:health_tips_list',
            icon='fa-heartbeat',
            active=is_active(
                vn,
                'health_tips:health_tips_list',
                'health_tips:health_tip_detail',
                'health_tips:edit_health_tip',
                'health_tips:delete_health_tip',
            ),
        ),
    ]
    if role in ('admin', 'staff', 'doctor'):
        items.append(
            nav_item(
                'Create Tip',
                'health_tips:create_health_tip',
                icon='fa-plus',
                active=vn == 'health_tips:create_health_tip',
            )
        )
    return enrich_subnav(items)


@register.inclusion_tag('components/sub_nav.html', takes_context=True)
def health_forms_services_subnav(context):
    vn = view_name(context['request'])
    items = [
        nav_item(
            'Health Forms',
            'health_forms_services:forms_list',
            icon='fa-heart-pulse',
            active=is_active(
                vn,
                'health_forms_services:forms_list',
                'health_forms_services:form_detail',
                'health_forms_services:edit_form',
            ),
        ),
        nav_item(
            'Dental Forms',
            'health_forms_services:dental_forms_list',
            icon='fa-tooth',
            active=is_active(
                vn,
                'health_forms_services:dental_forms_list',
                'health_forms_services:dental_form_detail',
                'health_forms_services:create_dental_form',
                'health_forms_services:edit_dental_form',
            ),
        ),
        nav_item(
            'Patient Charts',
            'health_forms_services:patient_chart_list',
            icon='fa-clipboard-user',
            active=is_active(
                vn,
                'health_forms_services:patient_chart_list',
                'health_forms_services:patient_chart_detail',
                'health_forms_services:create_patient_chart',
                'health_forms_services:edit_patient_chart',
            ),
        ),
        nav_item(
            'Dental Services',
            'health_forms_services:dental_services_list',
            icon='fa-teeth',
            active=is_active(
                vn,
                'health_forms_services:dental_services_list',
                'health_forms_services:dental_services_detail',
                'health_forms_services:create_dental_services',
                'health_forms_services:edit_dental_services',
            ),
        ),
        nav_item(
            'Prescriptions',
            'health_forms_services:prescription_list',
            icon='fa-prescription-bottle',
            active=is_active(
                vn,
                'health_forms_services:prescription_list',
                'health_forms_services:prescription_detail',
                'health_forms_services:create_prescription',
                'health_forms_services:edit_prescription',
            ),
        ),
    ]
    return enrich_subnav(items, always_show_nav=True)


@register.inclusion_tag('components/sub_nav.html', takes_context=True)
def analytics_subnav(context):
    request = context['request']
    user = request.user
    vn = view_name(request)
    home_url_name = analytics_home_url_name(user)
    items = [
        nav_item(
            'Dashboard',
            home_url_name,
            icon='fa-gauge-high',
            active=vn == home_url_name,
        )
    ]
    if user.role in ('staff', 'doctor', 'admin'):
        items.extend(
            [
                nav_item(
                    'Health Trends',
                    'analytics:health_trends',
                    icon='fa-chart-line',
                    active=vn == 'analytics:health_trends',
                ),
                nav_item(
                    'Predictive',
                    'analytics:predictive_analytics',
                    icon='fa-lightbulb',
                    active=is_active(vn, 'analytics:predictive_analytics', 'analytics:generate_insight'),
                ),
                nav_item(
                    'Resources',
                    'analytics:resource_utilization',
                    icon='fa-chart-column',
                    active=vn == 'analytics:resource_utilization',
                ),
                nav_item(
                    'Population',
                    'analytics:population_health',
                    icon='fa-people-group',
                    active=vn == 'analytics:population_health',
                ),
                nav_item(
                    'Academic',
                    'analytics:academic_correlation',
                    icon='fa-graduation-cap',
                    active=vn == 'analytics:academic_correlation',
                ),
            ]
        )
    if user.role == 'admin':
        items.extend(
            [
                nav_item(
                    'Compliance',
                    'analytics:compliance_reports',
                    icon='fa-shield-halved',
                    active=is_active(
                        vn,
                        'analytics:compliance_reports',
                        'analytics:compliance_report_detail',
                        'analytics:generate_compliance_report',
                    ),
                ),
                nav_item(
                    'Financial',
                    'analytics:financial_overview',
                    icon='fa-coins',
                    active=is_active(vn, 'analytics:financial_overview', 'analytics:financial_record_create'),
                ),
            ]
        )
    if role_matches(user.role, ROLE_PATIENT):
        return enrich_subnav([], nav_mb='mb-4')
    return enrich_subnav(items, always_show_nav=True, nav_mb='mb-4')


@register.inclusion_tag('components/sub_nav.html', takes_context=True)
def pharmacy_subnav(context):
    vn = view_name(context['request'])
    return enrich_subnav(
        [
            nav_item('Dashboard', 'pharmacy:dashboard', icon='fa-gauge-high', active=vn == 'pharmacy:dashboard'),
            nav_item('Medicines', 'pharmacy:medicine_list', icon='fa-capsules', active='medicine' in vn),
            nav_item('Categories', 'pharmacy:category_list', icon='fa-tags', active='category' in vn),
            nav_item('Batches', 'pharmacy:batch_list', icon='fa-boxes-stacked', active='batch' in vn),
            nav_item('Suppliers', 'pharmacy:supplier_list', icon='fa-truck-field', active='supplier' in vn),
            nav_item('Orders', 'pharmacy:purchase_order_list', icon='fa-file-invoice', active='purchase_order' in vn),
            nav_item(
                'Dispensing',
                'pharmacy:dispensing_list',
                icon='fa-hand-holding-medical',
                active='dispensing' in vn,
            ),
            nav_item('Adjustments', 'pharmacy:adjustment_list', icon='fa-sliders', active='adjustment' in vn),
            nav_item('Audit Log', 'pharmacy:audit_log_list', icon='fa-clipboard-list', active='audit_log' in vn),
            nav_item(
                'Reports',
                'pharmacy:compliance_report',
                icon='fa-chart-column',
                active='compliance_report' in vn or 'cost_analysis' in vn,
            ),
        ],
        always_show_nav=True,
    )


@register.inclusion_tag('components/sub_nav.html', takes_context=True)
def messaging_subnav(context):
    request = context['request']
    vn = view_name(request)
    user = request.user
    items = [
        nav_item(
            'Inbox',
            'messaging:inbox',
            icon='fa-inbox',
            active=is_active(vn, 'messaging:inbox', 'messaging:conversation_detail'),
        )
    ]
    if role_matches(user.role, ROLE_PATIENT, 'staff', 'doctor'):
        items.append(
            nav_item(
                'New Message',
                'messaging:start_conversation',
                icon='fa-pen-to-square',
                active=vn == 'messaging:start_conversation',
            )
        )
    return enrich_subnav(items)


@register.inclusion_tag('components/sub_nav.html', takes_context=True)
def settings_subnav(context):
    active = context.get('settings_subnav_active', 'hub')
    items = [
        nav_item('Overview', 'core:settings_hub', icon='fa-gauge-high', active=active == 'hub'),
        nav_item('Clinic', 'core:settings_clinic', icon='fa-hospital', active=active == 'clinic'),
        nav_item(
            'Roles',
            'core:settings_roles',
            icon='fa-user-shield',
            active=active in ('roles', 'role'),
        ),
        nav_item(
            'Academic',
            'core:settings_academic_hub',
            icon='fa-graduation-cap',
            active=active == 'academic',
        ),
        nav_item(
            'Appointments',
            'appointments:appointment_type_settings',
            icon='fa-calendar-check',
            active=active == 'appointments',
        ),
        nav_item('Audit log', 'core:settings_audit', icon='fa-clock-rotate-left', active=active == 'audit'),
        nav_item(
            'Clinical access',
            'core:clinical_access_log',
            icon='fa-shield-heart',
            active=active == 'clinical_audit',
        ),
    ]
    return enrich_subnav(items, always_show_nav=True)


def _users_list_crumb():
    return {
        'label': 'Users',
        'url': reverse('core:user_management'),
        'icon': 'fa-users-gear',
    }


def _user_management_breadcrumb_subnav(context, section_label, *, section_icon='fa-circle'):
    """Breadcrumb subnav for a specific user (detail, edit, audit, etc.)."""
    viewed_user = context.get('viewed_user')
    if not viewed_user:
        return breadcrumb_subnav(
            [_users_list_crumb(), {'label': section_label, 'icon': section_icon}],
        )

    name = (viewed_user.get_full_name() or '').strip() or viewed_user.email
    return breadcrumb_subnav(
        [
            _users_list_crumb(),
            {
                'label': name,
                'url': reverse('core:user_detail', kwargs={'user_id': viewed_user.pk}),
                'icon': 'fa-user',
            },
            {'label': section_label, 'icon': section_icon},
        ],
    )


@register.inclusion_tag('components/sub_nav.html', takes_context=True)
def core_admin_subnav(context):
    request = context['request']
    if request.user.role != 'admin':
        return enrich_subnav([])
    vn = view_name(request)

    if vn == 'core:user_detail':
        viewed_user = context.get('viewed_user')
        name = ((viewed_user.get_full_name() if viewed_user else '') or '').strip()
        if viewed_user and not name:
            name = viewed_user.email
        return breadcrumb_subnav(
            [
                _users_list_crumb(),
                {'label': name or 'User', 'icon': 'fa-user'},
            ],
        )

    if vn == 'core:user_edit':
        return _user_management_breadcrumb_subnav(
            context, 'Edit user', section_icon='fa-pen-to-square',
        )
    if vn == 'core:user_audit_log':
        return _user_management_breadcrumb_subnav(
            context, 'Audit log', section_icon='fa-clock-rotate-left',
        )
    if vn == 'core:patient_clinical_access_log':
        return _user_management_breadcrumb_subnav(
            context, 'Clinical access', section_icon='fa-shield-heart',
        )
    if vn == 'core:user_reset_password':
        return _user_management_breadcrumb_subnav(
            context, 'Reset password', section_icon='fa-key',
        )
    if vn == 'core:user_create':
        return breadcrumb_subnav(
            [
                _users_list_crumb(),
                {'label': 'Create user', 'icon': 'fa-user-plus'},
            ],
        )
    if vn == 'core:user_cleanup_stale':
        return breadcrumb_subnav(
            [
                _users_list_crumb(),
                {'label': 'Clean up', 'icon': 'fa-broom'},
            ],
        )
    if is_active(
        vn,
        'core:deleted_user_management',
        'core:deleted_user_bulk_action',
        'core:deleted_user_bulk_restore',
        'core:deleted_user_permanent_delete',
        'core:user_restore',
    ):
        return breadcrumb_subnav(
            [
                _users_list_crumb(),
                {'label': 'Deleted accounts', 'icon': 'fa-box-archive'},
            ],
        )

    active = 'user_management' in vn or is_active(
        vn,
        'core:user_create',
        'core:user_detail',
        'core:user_edit',
        'core:user_delete',
        'core:user_toggle_status',
        'core:user_reset_password',
        'core:user_audit_log',
        'core:user_cleanup_stale',
    )
    return enrich_subnav(
        [
            nav_item(
                'Users',
                'core:user_management',
                icon='fa-users-gear',
                active=active,
            )
        ]
    )
