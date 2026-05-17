"""Grouped layout for dental history (edit + detail views)."""

from __future__ import annotations

DENTAL_HISTORY_SECTIONS: list[dict] = [
    {
        'title': 'Previous Dental Visits',
        'icon': 'fa-calendar-check',
        'icon_class': 'text-primary-600',
        'fields': [
            {
                'name': 'first_dental_visit',
                'kind': 'checkbox',
                'display_label': 'First dental visit',
                'full_width': True,
            },
            {
                'name': 'last_dental_visit',
                'kind': 'date',
                'display_label': 'Last dental visit',
                'hide_if': 'first_dental_visit',
            },
            {
                'name': 'last_visit_reason',
                'kind': 'textarea',
                'display_label': 'Reason for last visit',
                'full_width': True,
                'hide_if': 'first_dental_visit',
            },
        ],
    },
    {
        'title': 'Teeth Extraction History',
        'icon': 'fa-tooth',
        'icon_class': 'text-primary-600',
        'fields': [
            {
                'name': 'teeth_extracted',
                'kind': 'checkbox',
                'display_label': 'Teeth extracted',
                'full_width': True,
            },
            {
                'name': 'extraction_when',
                'kind': 'text',
                'display_label': 'When extraction occurred',
                'show_if': 'teeth_extracted',
            },
        ],
    },
    {
        'title': 'Anesthesia Allergy',
        'icon': 'fa-syringe',
        'icon_class': 'text-danger-500',
        'fields': [
            {
                'name': 'anesthesia_allergy',
                'kind': 'checkbox',
                'display_label': 'Allergy to anesthesia',
                'full_width': True,
            },
            {
                'name': 'anesthesia_allergy_when',
                'kind': 'text',
                'display_label': 'When allergy occurred',
                'show_if': 'anesthesia_allergy',
            },
        ],
    },
    {
        'title': 'Dental Appliances',
        'icon': 'fa-prescription',
        'icon_class': 'text-primary-600',
        'fields': [
            {
                'name': 'dental_appliance',
                'kind': 'checkbox',
                'display_label': 'Wearing dental appliance',
                'full_width': True,
            },
            {
                'name': 'appliance_type',
                'kind': 'text',
                'display_label': 'Appliance type',
                'show_if': 'dental_appliance',
            },
        ],
    },
    {
        'title': 'Pain and Discomfort',
        'icon': 'fa-triangle-exclamation',
        'icon_class': 'text-warning-500',
        'fields': [
            {
                'name': 'pain_discomfort',
                'kind': 'checkbox',
                'display_label': 'Pain / discomfort',
                'full_width': True,
            },
            {
                'name': 'pain_location',
                'kind': 'textarea',
                'display_label': 'Pain location',
                'full_width': True,
                'show_if': 'pain_discomfort',
            },
        ],
    },
]
