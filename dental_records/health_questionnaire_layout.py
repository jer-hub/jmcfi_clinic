"""Grouped layout for health questionnaire (edit + detail views)."""

from __future__ import annotations

HEALTH_QUESTIONNAIRE_SECTIONS: list[dict] = [
    {
        'title': 'Hospital & Doctor History',
        'icon': 'fa-hospital',
        'icon_class': 'text-primary-600',
        'layout': 'visit_cards',
        'cards': [
            {
                'title': 'Last Hospital Confinement',
                'fields': [
                    {
                        'name': 'last_hospital_date',
                        'kind': 'date',
                        'display_label': 'Date',
                    },
                    {
                        'name': 'last_hospital_reason',
                        'kind': 'textarea',
                        'display_label': 'Reason',
                        'rows': 2,
                    },
                ],
            },
            {
                'title': 'Last Doctor Visit',
                'fields': [
                    {
                        'name': 'last_doctor_date',
                        'kind': 'date',
                        'display_label': 'Date',
                    },
                    {
                        'name': 'last_doctor_reason',
                        'kind': 'textarea',
                        'display_label': 'Reason',
                        'rows': 2,
                    },
                ],
            },
        ],
    },
    {
        'title': 'Medical Care & Medications',
        'icon': 'fa-notes-medical',
        'icon_class': 'text-primary-600',
        'layout': 'care_cards',
        'cards': [
            {
                'checkbox': 'doctor_care_2years',
                'checkbox_label': "Under doctor's care (last 2 years)",
                'followups': [
                    {
                        'name': 'doctor_care_reason',
                        'kind': 'textarea',
                        'display_label': 'Reason',
                        'rows': 2,
                        'show_if': 'doctor_care_2years',
                    },
                ],
            },
            {
                'checkbox': 'medications_2years',
                'checkbox_label': 'Taking medications (last 2 years)',
                'followups': [
                    {
                        'name': 'medications_for',
                        'kind': 'textarea',
                        'display_label': 'Medications',
                        'rows': 2,
                        'show_if': 'medications_2years',
                    },
                ],
            },
        ],
    },
    {
        'title': 'Symptoms & Conditions',
        'icon': 'fa-triangle-exclamation',
        'icon_class': 'text-warning-600',
        'layout': 'symptom_groups',
        'groups': [
            {
                'checkbox': 'excessive_bleeding',
                'checkbox_label': 'Excessive bleeding',
                'variant': 'danger',
                'followups': [
                    {
                        'name': 'excessive_bleeding_when',
                        'kind': 'text',
                        'display_label': 'When did it occur?',
                        'show_if': 'excessive_bleeding',
                    },
                ],
            },
            {
                'checkbox': 'easily_exhausted',
                'checkbox_label': 'Easily exhausted when walking',
                'variant': 'warning',
            },
            {
                'checkbox': 'swollen_ankles',
                'checkbox_label': 'Swollen ankles during the day',
                'variant': 'warning',
            },
            {
                'checkbox': 'more_than_2_pillows',
                'checkbox_label': 'Uses more than 2 pillows',
                'variant': 'warning',
                'followups': [
                    {
                        'name': 'pillows_reason',
                        'kind': 'textarea',
                        'display_label': 'Reason',
                        'rows': 2,
                        'show_if': 'more_than_2_pillows',
                    },
                ],
            },
            {
                'checkbox': 'tumor_cancer',
                'checkbox_label': 'Tumor / cancer diagnosis',
                'variant': 'danger',
                'followups': [
                    {
                        'name': 'tumor_cancer_when',
                        'kind': 'text',
                        'display_label': 'When diagnosed?',
                        'show_if': 'tumor_cancer',
                    },
                ],
            },
        ],
    },
    {
        'title': "Women's Health",
        'icon': 'fa-venus',
        'icon_class': 'text-info-600',
        'layout': 'womens_groups',
        'groups': [
            {
                'checkbox': 'is_pregnant',
                'checkbox_label': 'Pregnant',
                'variant': 'info',
                'followups': [
                    {
                        'name': 'pregnancy_months',
                        'kind': 'number',
                        'display_label': 'Months pregnant',
                        'show_if': 'is_pregnant',
                    },
                ],
            },
            {
                'checkbox': 'birth_control_pills',
                'checkbox_label': 'Taking birth control pills',
                'variant': 'info',
                'followups': [
                    {
                        'name': 'birth_control_specify',
                        'kind': 'text',
                        'display_label': 'Specify',
                        'show_if': 'birth_control_pills',
                    },
                ],
            },
            {
                'checkbox': 'anticipate_pregnancy',
                'checkbox_label': 'Anticipating pregnancy',
                'variant': 'info',
            },
            {
                'checkbox': 'having_period',
                'checkbox_label': 'Currently having period',
                'variant': 'info',
            },
        ],
    },
]

SYMPTOM_CHIP_CLASSES = {
    'danger': {
        'wrap': 'bg-danger-50 border-danger-100',
        'title': 'text-danger-800',
        'detail': 'text-danger-600',
    },
    'warning': {
        'wrap': 'bg-warning-50 border-warning-100',
        'title': 'text-warning-800',
        'detail': 'text-warning-600',
    },
    'info': {
        'wrap': 'bg-info-50 border-info-100',
        'title': 'text-info-800',
        'detail': 'text-info-600',
    },
}
