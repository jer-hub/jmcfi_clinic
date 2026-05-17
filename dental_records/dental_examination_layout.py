"""Grouped layout for dental examination (edit + detail views)."""

from __future__ import annotations

DENTAL_EXAMINATION_SECTIONS: list[dict] = [
    {
        'title': 'Extraoral Examination',
        'icon': 'fa-face-smile',
        'icon_class': 'text-primary-600',
        'fields': [
            {'name': 'facial_symmetry', 'display_label': 'Facial Symmetry & Profile'},
            {'name': 'cutaneous_areas', 'display_label': 'Cutaneous Areas (Skin)'},
            {'name': 'eyes', 'display_label': 'Eyes'},
            {'name': 'lymph_nodes', 'display_label': 'Lymph Nodes'},
            {'name': 'tmj', 'display_label': 'TMJ'},
        ],
    },
    {
        'title': 'Intraoral Examination',
        'icon': 'fa-teeth-open',
        'icon_class': 'text-primary-600',
        'fields': [
            {'name': 'buccal_labial_mucosa', 'display_label': 'Buccal / Labial Mucosa'},
            {'name': 'gingiva', 'display_label': 'Gingiva'},
            {'name': 'palate_hard', 'display_label': 'Palate (Hard)'},
            {'name': 'palate_soft', 'display_label': 'Palate (Soft)'},
            {'name': 'tongue', 'display_label': 'Tongue'},
            {'name': 'salivary_flow', 'display_label': 'Salivary Flow'},
            {'name': 'oral_hygiene', 'display_label': 'Oral Hygiene'},
            {'name': 'lips', 'display_label': 'Lips'},
        ],
    },
]
