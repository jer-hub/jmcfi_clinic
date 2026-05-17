from django import template

from dental_records.dental_examination_layout import DENTAL_EXAMINATION_SECTIONS
from dental_records.dental_history_layout import DENTAL_HISTORY_SECTIONS
from dental_records.health_questionnaire_layout import (
    HEALTH_QUESTIONNAIRE_SECTIONS,
    SYMPTOM_CHIP_CLASSES,
)
from dental_records.systems_review_layout import (
    DETAIL_CHIP_CLASSES,
    DETAIL_ICON_CLASSES,
    SYSTEMS_REVIEW_SECTIONS,
)

register = template.Library()


@register.inclusion_tag('dental_records/partials/_systems_review_form.html')
def systems_review_form_sections(form):
    sections = []
    for section in SYSTEMS_REVIEW_SECTIONS:
        sections.append(
            {
                **section,
                'icon_class': DETAIL_ICON_CLASSES.get(section['variant'], 'text-primary-600'),
                'bound_fields': [form[field_name] for field_name in section['fields']],
            }
        )
    return {
        'sections': sections,
        'allergies_field': form['allergies'],
        'other_conditions_field': form['other_conditions'],
    }


@register.inclusion_tag('dental_records/partials/_systems_review_display.html')
def systems_review_display(systems_review):
    sections = []
    for section in SYSTEMS_REVIEW_SECTIONS:
        variant = section['variant']
        chips = DETAIL_CHIP_CLASSES.get(variant, DETAIL_CHIP_CLASSES['muted'])
        active_fields = []
        for field_name in section['fields']:
            if getattr(systems_review, field_name, False):
                model_field = systems_review._meta.get_field(field_name)
                active_fields.append(
                    {
                        'label': model_field.verbose_name.title(),
                    }
                )
        sections.append(
            {
                **section,
                'icon_class': DETAIL_ICON_CLASSES.get(variant, 'text-muted-500'),
                'chip_wrap': chips['wrap'],
                'chip_icon': chips['icon'],
                'active_fields': active_fields,
                'has_active': bool(active_fields),
            }
        )
    return {
        'sections': sections,
        'systems_review': systems_review,
        'has_other_conditions': bool((systems_review.other_conditions or '').strip()),
    }


def _history_section_has_data(history, section: dict) -> bool:
    for field in section['fields']:
        name = field['name']
        value = getattr(history, name, None)
        if field['kind'] == 'checkbox':
            if value:
                return True
        elif value not in (None, ''):
            return True
    return False


def _history_display_value(history, field: dict) -> str:
    value = getattr(history, field['name'], None)
    if field['kind'] == 'checkbox':
        return 'Yes' if value else 'No'
    if field['kind'] == 'date' and value:
        return value.strftime('%b %d, %Y')
    return str(value) if value else ''


@register.inclusion_tag('dental_records/partials/_dental_history_form.html')
def dental_history_form_sections(form):
    toggle_names = {
        field['name']
        for section in DENTAL_HISTORY_SECTIONS
        for field in section['fields']
        if field['kind'] == 'checkbox'
    }
    toggles = {
        name: bool(form[name].value())
        for name in toggle_names
    }
    sections = []
    for section in DENTAL_HISTORY_SECTIONS:
        bound = []
        for field_meta in section['fields']:
            bound.append({**field_meta, 'bound': form[field_meta['name']]})
        sections.append({**section, 'fields': bound})
    return {'sections': sections, 'toggles': toggles}


@register.inclusion_tag('dental_records/partials/_dental_history_display.html')
def dental_history_display(dental_history):
    sections = []
    for section in DENTAL_HISTORY_SECTIONS:
        has_data = _history_section_has_data(dental_history, section)
        items = []
        if has_data:
            for field in section['fields']:
                value = getattr(dental_history, field['name'], None)
                if field['kind'] == 'checkbox':
                    items.append(
                        {
                            'label': field['display_label'],
                            'value': 'Yes' if value else 'No',
                            'emphasis': True,
                        }
                    )
                elif field['kind'] == 'date' and field['name'] == 'last_dental_visit':
                    items.append(
                        {
                            'label': field['display_label'],
                            'value': _history_display_value(dental_history, field) or '—',
                            'emphasis': False,
                        }
                    )
                elif value not in (None, ''):
                    items.append(
                        {
                            'label': field['display_label'],
                            'value': _history_display_value(dental_history, field),
                            'emphasis': False,
                            'full_width': field.get('full_width', False),
                        }
                    )
        sections.append({**section, 'items': items, 'has_data': has_data})
    return {'sections': sections}


def _hq_toggle_names() -> set[str]:
    names: set[str] = set()
    for section in HEALTH_QUESTIONNAIRE_SECTIONS:
        if section['layout'] == 'care_cards':
            for card in section['cards']:
                names.add(card['checkbox'])
        elif section['layout'] in ('symptom_groups', 'womens_groups'):
            for group in section['groups']:
                names.add(group['checkbox'])
    return names


def _bind_hq_field(form, field_meta: dict) -> dict:
    return {**field_meta, 'bound': form[field_meta['name']]}


@register.inclusion_tag('dental_records/partials/_health_questionnaire_form.html')
def health_questionnaire_form_sections(form):
    toggles = {name: bool(form[name].value()) for name in _hq_toggle_names()}
    sections = []
    for section in HEALTH_QUESTIONNAIRE_SECTIONS:
        payload = {**section}
        if section['layout'] == 'visit_cards':
            cards = []
            for card in section['cards']:
                cards.append(
                    {
                        **card,
                        'fields': [_bind_hq_field(form, field) for field in card['fields']],
                    }
                )
            payload['cards'] = cards
        elif section['layout'] == 'care_cards':
            cards = []
            for card in section['cards']:
                cards.append(
                    {
                        **card,
                        'checkbox_bound': form[card['checkbox']],
                        'followups': [_bind_hq_field(form, field) for field in card.get('followups', [])],
                    }
                )
            payload['cards'] = cards
        else:
            groups = []
            for group in section['groups']:
                groups.append(
                    {
                        **group,
                        'checkbox_bound': form[group['checkbox']],
                        'followups': [_bind_hq_field(form, field) for field in group.get('followups', [])],
                    }
                )
            payload['groups'] = groups
        sections.append(payload)
    return {'sections': sections, 'toggles': toggles}


@register.inclusion_tag('dental_records/partials/_health_questionnaire_display.html')
def health_questionnaire_display(health_questionnaire):
  hq = health_questionnaire
  sections = []

  hospital_cards = []
  if hq.last_hospital_date or hq.last_hospital_reason:
      hospital_cards.append(
          {
              'title': 'Last Hospital Confinement',
              'date': hq.last_hospital_date.strftime('%b %d, %Y') if hq.last_hospital_date else '—',
              'detail': (hq.last_hospital_reason or '').strip() or None,
          }
      )
  if hq.last_doctor_date or hq.last_doctor_reason:
      hospital_cards.append(
          {
              'title': 'Last Doctor Visit',
              'date': hq.last_doctor_date.strftime('%b %d, %Y') if hq.last_doctor_date else '—',
              'detail': (hq.last_doctor_reason or '').strip() or None,
          }
      )
  sections.append(
      {
          'title': 'Hospital & Doctor History',
          'icon': 'fa-hospital',
          'icon_class': 'text-primary-600',
          'layout': 'visit_cards',
          'cards': hospital_cards,
          'has_data': bool(hospital_cards),
      }
  )

  care_cards = []
  if hq.doctor_care_2years:
      care_cards.append(
          {
              'title': "Under Doctor's Care (Last 2 Years)",
              'detail': (hq.doctor_care_reason or '').strip() or None,
          }
      )
  if hq.medications_2years:
      care_cards.append(
          {
              'title': 'Medications (Last 2 Years)',
              'detail': (hq.medications_for or '').strip() or None,
          }
      )
  sections.append(
      {
          'title': 'Medical Care & Medications',
          'icon': 'fa-notes-medical',
          'icon_class': 'text-primary-600',
          'layout': 'care_cards',
          'cards': care_cards,
          'has_data': bool(care_cards),
      }
  )

  symptom_chips = []
  symptom_defs = [
      ('excessive_bleeding', 'Excessive Bleeding', 'danger', hq.excessive_bleeding_when),
      ('easily_exhausted', 'Easily Exhausted', 'warning', None),
      ('swollen_ankles', 'Swollen Ankles', 'warning', None),
      ('more_than_2_pillows', 'Uses More Than 2 Pillows', 'warning', hq.pillows_reason),
      ('tumor_cancer', 'Tumor / Cancer Diagnosis', 'danger', hq.tumor_cancer_when),
  ]
  for field_name, label, variant, detail in symptom_defs:
      if getattr(hq, field_name):
          styles = SYMPTOM_CHIP_CLASSES[variant]
          detail_text = (detail or '').strip() if detail else None
          if detail_text == '':
              detail_text = None
          symptom_chips.append(
              {
                  'label': label,
                  'detail': detail_text,
                  'wrap': styles['wrap'],
                  'title_class': styles['title'],
                  'detail_class': styles['detail'],
              }
          )
  sections.append(
      {
          'title': 'Symptoms & Conditions',
          'icon': 'fa-triangle-exclamation',
          'icon_class': 'text-warning-600',
          'layout': 'symptom_groups',
          'chips': symptom_chips,
          'has_data': bool(symptom_chips),
      }
  )

  womens_chips = []
  womens_defs = [
      ('is_pregnant', 'Pregnant', f'{hq.pregnancy_months} months' if hq.is_pregnant and hq.pregnancy_months else None),
      ('birth_control_pills', 'Taking Birth Control Pills', (hq.birth_control_specify or '').strip() or None),
      ('anticipate_pregnancy', 'Anticipating Pregnancy', None),
      ('having_period', 'Currently Having Period', None),
  ]
  for field_name, label, detail in womens_defs:
      if getattr(hq, field_name):
          styles = SYMPTOM_CHIP_CLASSES['info']
          if field_name == 'is_pregnant' and hq.pregnancy_months:
              detail = f'{hq.pregnancy_months} months'
          detail_text = (detail or '').strip() if isinstance(detail, str) else detail
          if detail_text == '':
              detail_text = None
          womens_chips.append(
              {
                  'label': label,
                  'detail': detail_text,
                  'wrap': styles['wrap'],
                  'title_class': styles['title'],
                  'detail_class': styles['detail'],
              }
          )
  sections.append(
      {
          'title': "Women's Health",
          'icon': 'fa-venus',
          'icon_class': 'text-info-600',
          'layout': 'womens_groups',
          'chips': womens_chips,
          'has_data': bool(womens_chips),
      }
  )

  return {'sections': sections}


def _exam_section_has_data(examination, section: dict) -> bool:
    for field in section['fields']:
        value = getattr(examination, field['name'], None)
        if value not in (None, ''):
            return True
    return False


def _exam_display_value(examination, field_name: str) -> str:
    value = getattr(examination, field_name, None)
    return str(value).strip() if value else '—'


@register.inclusion_tag('dental_records/partials/_dental_examination_form.html')
def dental_examination_form_sections(form):
    sections = []
    for section in DENTAL_EXAMINATION_SECTIONS:
        fields = [
            {**field_meta, 'bound': form[field_meta['name']]}
            for field_meta in section['fields']
        ]
        sections.append({**section, 'fields': fields})
    return {'sections': sections}


@register.inclusion_tag('dental_records/partials/_dental_examination_display.html')
def dental_examination_display(examination):
    sections = []
    for section in DENTAL_EXAMINATION_SECTIONS:
        has_data = _exam_section_has_data(examination, section)
        items = []
        if has_data:
            for field in section['fields']:
                items.append(
                    {
                        'label': field['display_label'],
                        'value': _exam_display_value(examination, field['name']),
                    }
                )
        sections.append({**section, 'items': items, 'has_data': has_data})
    return {'sections': sections}
