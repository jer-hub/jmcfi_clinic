from django import template
register = template.Library()


@register.filter(name='dict_key')
def dict_key(d, key):
    """Look up a key in a dict or mapping-like object (e.g., Django form instance),
    returning None if missing or on error."""
    if d is None:
        return None
    try:
        # Prefer .get() for dicts, fall back to __getitem__ for forms & similar
        if hasattr(d, 'get'):
            return d.get(key)
        return d[key]
    except (KeyError, AttributeError, TypeError):
        return None


@register.filter(name='strip_diagnosis_medications')
def strip_diagnosis_medications(value):
    """Return diagnosis text from prescription body without section markers."""
    from health_forms_services.forms import split_prescription_body

    sections = split_prescription_body(value or '')
    return sections['diagnosis']


@register.filter(name='prescription_body_sections')
def prescription_body_sections(value):
    """Parse prescription body into diagnosis, medications, and instructions."""
    from health_forms_services.forms import split_prescription_body

    return split_prescription_body(value or '')
