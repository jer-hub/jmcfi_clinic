import re
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
    """Strip 'Diagnosis:' prefix and everything after 'Medications:' from the body text.
    
    The medications are now displayed separately in the Prescribed Medications section,
    so we remove them from the prescription notes display.
    """
    if not value:
        return value
    
    # Remove "Diagnosis:" prefix (case-insensitive)
    text = re.sub(r'^Diagnosis:\s*', '', value, flags=re.IGNORECASE)
    
    # Remove everything from "Medications:" onwards (case-insensitive)
    text = re.sub(r'\n?Medications:.*', '', text, flags=re.IGNORECASE | re.DOTALL)
    
    return text.strip()
