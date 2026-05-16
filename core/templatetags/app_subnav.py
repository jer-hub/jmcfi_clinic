"""Inclusion tags that render `components/sub_nav.html` with per-app items."""

from django import template
from django.urls import reverse

from core.utils import analytics_home_url_name

register = template.Library()


@register.simple_tag(takes_context=True)
def analytics_home_url(context):
    return reverse(analytics_home_url_name(context['request'].user))


def _enrich_context(items, *, always_show_nav=False):
    """Return the template context, adding breadcrumb data when on a sub-page.

    A "sub-page" is any page whose active item is not the first item in the
    list. When detected, the template renders breadcrumbs (parent → current)
    instead of the full nav strip.

    Set *always_show_nav* for apps that use peer-level tabs (e.g. pharmacy,
    analytics) where all items are top-level sections.
    """
    ctx = {'items': items, 'show_breadcrumbs': False}

    if always_show_nav or len(items) < 2:
        return ctx

    parent = items[0]
    for item in items[1:]:
        if item.get('active'):
            ctx['show_breadcrumbs'] = True
            ctx['bc_crumbs'] = [
                {'label': parent['label'], 'url': parent['url'], 'icon': parent.get('icon', '')},
                {'label': item['label'], 'icon': item.get('icon', '')},
            ]
            break

    return ctx


@register.inclusion_tag('components/sub_nav.html', takes_context=True)
def appointments_subnav(context):
    request = context['request']
    vn = request.resolver_match.view_name
    role = request.user.role
    items = [
        {
            'label': 'Appointments',
            'url': reverse('appointments:appointment_list'),
            'icon': 'fa-calendar-days',
            'active': vn == 'appointments:appointment_list',
        }
    ]
    if role == 'student':
        items.append(
            {
                'label': 'Schedule',
                'url': reverse('appointments:schedule_appointment'),
                'icon': 'fa-plus',
                'active': vn == 'appointments:schedule_appointment',
            }
        )
    elif role in ('doctor', 'staff'):
        items.append(
            {
                'label': 'Schedule for Student',
                'url': reverse('appointments:schedule_for_student'),
                'icon': 'fa-plus',
                'active': vn == 'appointments:schedule_for_student',
            }
        )
    if role == 'admin':
        items.append(
            {
                'label': 'Settings',
                'url': reverse('appointments:appointment_type_settings'),
                'icon': 'fa-gear',
                'active': vn
                in ('appointments:appointment_type_settings', 'appointments:edit_appointment_type_default'),
            }
        )
    return _enrich_context(items, always_show_nav=True)


@register.inclusion_tag('components/sub_nav.html', takes_context=True)
def medical_records_subnav(context):
    request = context['request']
    vn = request.resolver_match.view_name
    role = request.user.role
    items = [
        {
            'label': 'Medical Records',
            'url': reverse('medical_records:medical_records'),
            'icon': 'fa-file-medical',
            'active': vn == 'medical_records:medical_records',
        }
    ]
    if role in ('staff', 'doctor'):
        items.append(
            {
                'label': 'New Record',
                'url': reverse('medical_records:create_medical_record_for_student'),
                'icon': 'fa-plus',
                'active': vn
                in (
                    'medical_records:create_medical_record_for_student',
                    'medical_records:create_medical_record',
                ),
            }
        )
    ctx = _enrich_context(items, always_show_nav=True)
    ctx['nav_mb'] = 'mb-4'
    return ctx


@register.inclusion_tag('components/sub_nav.html', takes_context=True)
def dental_records_subnav(context):
    request = context['request']
    vn = request.resolver_match.view_name
    role = request.user.role
    items = [
        {
            'label': 'Dental Records',
            'url': reverse('dental_records:dental_record_list'),
            'icon': 'fa-tooth',
            'active': vn == 'dental_records:dental_record_list',
        }
    ]
    if role != 'student':
        items.append(
            {
                'label': 'New Record',
                'url': reverse('dental_records:dental_record_create'),
                'icon': 'fa-plus',
                'active': vn == 'dental_records:dental_record_create',
            }
        )
    ctx = _enrich_context(items, always_show_nav=True)
    ctx['nav_mb'] = 'mb-4'
    return ctx


def _document_requests_list_crumb():
    return {
        'label': 'Requests',
        'url': reverse('document_request:document_requests'),
        'icon': 'fa-file-medical',
    }


def _document_request_breadcrumb_subnav(crumbs):
    return {
        'show_breadcrumbs': True,
        'bc_crumbs': crumbs,
        'nav_mb': 'mb-4',
        'items': [],
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
    vn = request.resolver_match.view_name

    if vn == 'document_request:document_request_detail':
        return _document_request_breadcrumb_subnav(
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
        return _document_request_breadcrumb_subnav(crumbs)

    items = [
        {
            'label': 'Requests',
            'url': reverse('document_request:document_requests'),
            'icon': 'fa-file-medical',
            'active': vn in (
                'document_request:document_requests',
                'document_request:process_document',
                'document_request:view_document',
            ),
        },
    ]
    if getattr(request.user, 'role', None) in ('student', 'doctor', 'staff', 'admin'):
        items.append(
            {
                'label': 'New Request',
                'url': reverse('document_request:request_document'),
                'icon': 'fa-plus',
                'active': vn == 'document_request:request_document',
            }
        )
    if getattr(request.user, 'role', None) in ('doctor', 'staff', 'admin'):
        items.append(
            {
                'label': 'My Signature',
                'url': reverse('document_request:clinician_signature'),
                'icon': 'fa-signature',
                'active': vn == 'document_request:clinician_signature',
            }
        )
    ctx = _enrich_context(items, always_show_nav=True)
    ctx['nav_mb'] = 'mb-4'
    return ctx


@register.inclusion_tag('components/sub_nav.html', takes_context=True)
def feedback_subnav(context):
    request = context['request']
    vn = request.resolver_match.view_name
    role = request.user.role
    items = [
        {
            'label': 'Feedback',
            'url': reverse('feedback:feedback_list'),
            'icon': 'fa-comments',
            'active': vn == 'feedback:feedback_list',
        },
        {
            'label': 'Submit',
            'url': reverse('feedback:submit_feedback'),
            'icon': 'fa-pen',
            'active': vn in ('feedback:submit_feedback', 'feedback:submit_feedback_appointment'),
        },
    ]
    if role in ('admin', 'staff', 'doctor'):
        items.append(
            {
                'label': 'Statistics',
                'url': reverse('feedback:feedback_stats'),
                'icon': 'fa-chart-pie',
                'active': vn == 'feedback:feedback_stats',
            }
        )
    return _enrich_context(items)


@register.inclusion_tag('components/sub_nav.html', takes_context=True)
def health_tips_subnav(context):
    request = context['request']
    vn = request.resolver_match.view_name
    role = request.user.role
    items = [
        {
            'label': 'Health Tips',
            'url': reverse('health_tips:health_tips_list'),
            'icon': 'fa-heartbeat',
            'active': vn
            in (
                'health_tips:health_tips_list',
                'health_tips:health_tip_detail',
                'health_tips:edit_health_tip',
                'health_tips:delete_health_tip',
            ),
        },
    ]
    if role in ('admin', 'staff', 'doctor'):
        items.append(
            {
                'label': 'Create Tip',
                'url': reverse('health_tips:create_health_tip'),
                'icon': 'fa-plus',
                'active': vn == 'health_tips:create_health_tip',
            }
        )
    return _enrich_context(items)


@register.inclusion_tag('components/sub_nav.html', takes_context=True)
def health_forms_services_subnav(context):
    request = context['request']
    vn = request.resolver_match.view_name
    items = [
        {
            'label': 'Health Forms',
            'url': reverse('health_forms_services:forms_list'),
            'icon': 'fa-heart-pulse',
            'active': vn in ('health_forms_services:forms_list', 'health_forms_services:form_detail', 'health_forms_services:edit_form'),
        },
        {
            'label': 'Dental Forms',
            'url': reverse('health_forms_services:dental_forms_list'),
            'icon': 'fa-tooth',
            'active': vn
            in (
                'health_forms_services:dental_forms_list',
                'health_forms_services:dental_form_detail',
                'health_forms_services:create_dental_form',
                'health_forms_services:edit_dental_form',
            ),
        },
        {
            'label': 'Patient Charts',
            'url': reverse('health_forms_services:patient_chart_list'),
            'icon': 'fa-clipboard-user',
            'active': vn
            in (
                'health_forms_services:patient_chart_list',
                'health_forms_services:patient_chart_detail',
                'health_forms_services:create_patient_chart',
                'health_forms_services:edit_patient_chart',
            ),
        },
        {
            'label': 'Dental Services',
            'url': reverse('health_forms_services:dental_services_list'),
            'icon': 'fa-teeth',
            'active': vn
            in (
                'health_forms_services:dental_services_list',
                'health_forms_services:dental_services_detail',
                'health_forms_services:create_dental_services',
                'health_forms_services:edit_dental_services',
            ),
        },
        {
            'label': 'Prescriptions',
            'url': reverse('health_forms_services:prescription_list'),
            'icon': 'fa-prescription-bottle',
            'active': vn
            in (
                'health_forms_services:prescription_list',
                'health_forms_services:prescription_detail',
                'health_forms_services:create_prescription',
                'health_forms_services:edit_prescription',
            ),
        },
    ]
    return _enrich_context(items, always_show_nav=True)


@register.inclusion_tag('components/sub_nav.html', takes_context=True)
def analytics_subnav(context):
    request = context['request']
    user = request.user
    vn = request.resolver_match.view_name
    home_url_name = analytics_home_url_name(user)
    items = [
        {
            'label': 'Dashboard',
            'url': reverse(home_url_name),
            'icon': 'fa-gauge-high',
            'active': vn == home_url_name,
        }
    ]
    if user.role in ('staff', 'doctor', 'admin'):
        items.extend(
            [
                {
                    'label': 'Health Trends',
                    'url': reverse('analytics:health_trends'),
                    'icon': 'fa-chart-line',
                    'active': vn == 'analytics:health_trends',
                },
                {
                    'label': 'Predictive',
                    'url': reverse('analytics:predictive_analytics'),
                    'icon': 'fa-lightbulb',
                    'active': vn in ('analytics:predictive_analytics', 'analytics:generate_insight'),
                },
                {
                    'label': 'Resources',
                    'url': reverse('analytics:resource_utilization'),
                    'icon': 'fa-chart-column',
                    'active': vn == 'analytics:resource_utilization',
                },
                {
                    'label': 'Population',
                    'url': reverse('analytics:population_health'),
                    'icon': 'fa-people-group',
                    'active': vn == 'analytics:population_health',
                },
                {
                    'label': 'Academic',
                    'url': reverse('analytics:academic_correlation'),
                    'icon': 'fa-graduation-cap',
                    'active': vn == 'analytics:academic_correlation',
                },
            ]
        )
    if user.role == 'admin':
        items.extend(
            [
                {
                    'label': 'Compliance',
                    'url': reverse('analytics:compliance_reports'),
                    'icon': 'fa-shield-halved',
                    'active': vn
                    in (
                        'analytics:compliance_reports',
                        'analytics:compliance_report_detail',
                        'analytics:generate_compliance_report',
                    ),
                },
                {
                    'label': 'Financial',
                    'url': reverse('analytics:financial_overview'),
                    'icon': 'fa-coins',
                    'active': vn in ('analytics:financial_overview', 'analytics:financial_record_create'),
                },
            ]
        )
    if user.role == 'student':
        return {'items': [], 'show_breadcrumbs': False, 'nav_mb': 'mb-4'}
    ctx = _enrich_context(items, always_show_nav=True)
    ctx['nav_mb'] = 'mb-4'
    return ctx


@register.inclusion_tag('components/sub_nav.html', takes_context=True)
def pharmacy_subnav(context):
    request = context['request']
    vn = request.resolver_match.view_name
    return _enrich_context(
        [
            {
                'label': 'Dashboard',
                'url': reverse('pharmacy:dashboard'),
                'icon': 'fa-gauge-high',
                'active': vn == 'pharmacy:dashboard',
            },
            {
                'label': 'Medicines',
                'url': reverse('pharmacy:medicine_list'),
                'icon': 'fa-capsules',
                'active': 'medicine' in vn,
            },
            {
                'label': 'Categories',
                'url': reverse('pharmacy:category_list'),
                'icon': 'fa-tags',
                'active': 'category' in vn,
            },
            {
                'label': 'Batches',
                'url': reverse('pharmacy:batch_list'),
                'icon': 'fa-boxes-stacked',
                'active': 'batch' in vn,
            },
            {
                'label': 'Suppliers',
                'url': reverse('pharmacy:supplier_list'),
                'icon': 'fa-truck-field',
                'active': 'supplier' in vn,
            },
            {
                'label': 'Orders',
                'url': reverse('pharmacy:purchase_order_list'),
                'icon': 'fa-file-invoice',
                'active': 'purchase_order' in vn,
            },
            {
                'label': 'Dispensing',
                'url': reverse('pharmacy:dispensing_list'),
                'icon': 'fa-hand-holding-medical',
                'active': 'dispensing' in vn,
            },
            {
                'label': 'Adjustments',
                'url': reverse('pharmacy:adjustment_list'),
                'icon': 'fa-sliders',
                'active': 'adjustment' in vn,
            },
            {
                'label': 'Audit Log',
                'url': reverse('pharmacy:audit_log_list'),
                'icon': 'fa-clipboard-list',
                'active': 'audit_log' in vn,
            },
            {
                'label': 'Reports',
                'url': reverse('pharmacy:compliance_report'),
                'icon': 'fa-chart-column',
                'active': 'compliance_report' in vn or 'cost_analysis' in vn,
            },
        ],
        always_show_nav=True,
    )


@register.inclusion_tag('components/sub_nav.html', takes_context=True)
def messaging_subnav(context):
    request = context['request']
    vn = request.resolver_match.view_name
    user = request.user
    items = [
        {
            'label': 'Inbox',
            'url': reverse('messaging:inbox'),
            'icon': 'fa-inbox',
            'active': vn in ('messaging:inbox', 'messaging:conversation_detail'),
        }
    ]
    if user.role in ('student', 'staff', 'doctor', 'admin'):
        items.append(
            {
                'label': 'New Message',
                'url': reverse('messaging:start_conversation'),
                'icon': 'fa-pen-to-square',
                'active': vn == 'messaging:start_conversation',
            }
        )
    return _enrich_context(items)


@register.inclusion_tag('components/sub_nav.html', takes_context=True)
def core_admin_subnav(context):
    request = context['request']
    if request.user.role != 'admin':
        return _enrich_context([])
    vn = request.resolver_match.view_name
    active = 'user_management' in vn or vn in (
        'core:user_create',
        'core:user_detail',
        'core:user_edit',
        'core:user_delete',
        'core:user_toggle_status',
        'core:user_reset_password',
        'core:user_audit_log',
        'core:user_cleanup_stale',
        'core:user_deleted_list',
    )
    return _enrich_context(
        [
            {
                'label': 'Users',
                'url': reverse('core:user_management'),
                'icon': 'fa-users-gear',
                'active': active,
            }
        ]
    )
