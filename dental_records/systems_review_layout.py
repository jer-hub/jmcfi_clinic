"""Grouped layout for dental systems review (edit + detail views)."""

from __future__ import annotations

# variant drives detail chip colors: danger | info | primary | warning | success | muted
SYSTEMS_REVIEW_SECTIONS: list[dict] = [
    {
        'title': 'Cardiovascular',
        'icon': 'fa-heart',
        'variant': 'danger',
        'fields': [
            'heart_disease',
            'hypertension',
            'rheumatic_heart_disease',
            'heart_surgery',
            'stroke',
        ],
    },
    {
        'title': 'Respiratory',
        'icon': 'fa-lungs',
        'variant': 'info',
        'fields': [
            'asthma',
            'emphysema',
            'cough',
            'pneumonia',
            'hay_fever',
            'sinus_problem',
            'tuberculosis',
        ],
    },
    {
        'title': 'Blood / Hematologic',
        'icon': 'fa-droplet',
        'variant': 'primary',
        'fields': [
            'anemia',
            'bleeding_tendencies',
            'hemophilia',
            'sickle_cell_anemia',
            'blood_transfusion',
        ],
    },
    {
        'title': 'Endocrine / Metabolic',
        'icon': 'fa-balance-scale',
        'variant': 'warning',
        'fields': ['diabetes', 'thyroid_problem', 'glandular_problem'],
    },
    {
        'title': 'Gastrointestinal',
        'icon': 'fa-stomach',
        'variant': 'success',
        'fields': ['stomach_ulcer', 'liver_problem', 'hepatitis_a', 'hepatitis_b'],
    },
    {
        'title': 'Other Systems & Conditions',
        'icon': 'fa-virus',
        'variant': 'muted',
        'fields': [
            'kidney_problem',
            'hiv_aids',
            'scarlet_fever',
            'std',
            'brain_injury',
            'psychiatric_visit',
            'arthritis',
            'rheumatism',
            'tmj_problem',
            'cancer_treatment',
            'glaucoma',
            'cold_sores',
            'bruising',
            'drug_addiction',
            'ear_infection',
            'hyperactivity',
            'skin_disorder',
            'development_problems',
            'aspirin_medication',
            'cortisone_medication',
        ],
    },
]

DETAIL_CHIP_CLASSES = {
    'danger': {
        'wrap': 'bg-danger-50 border-danger-100',
        'icon': 'text-danger-500',
    },
    'info': {
        'wrap': 'bg-info-50 border-info-100',
        'icon': 'text-info-500',
    },
    'primary': {
        'wrap': 'bg-primary-50 border-primary-100',
        'icon': 'text-primary-500',
    },
    'warning': {
        'wrap': 'bg-warning-50 border-warning-100',
        'icon': 'text-warning-500',
    },
    'success': {
        'wrap': 'bg-success-50 border-success-100',
        'icon': 'text-success-500',
    },
    'muted': {
        'wrap': 'bg-gray-50 border-gray-200',
        'icon': 'text-muted-500',
    },
}

DETAIL_ICON_CLASSES = {
    'danger': 'text-danger-500',
    'info': 'text-info-500',
    'primary': 'text-primary-600',
    'warning': 'text-warning-500',
    'success': 'text-success-500',
    'muted': 'text-muted-500',
}
