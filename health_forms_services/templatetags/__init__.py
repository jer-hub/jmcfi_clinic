from django import template

register = template.Library()


@register.filter(name='dict_key')
def dict_key(d, key):
    """Look up a key in a dict or mapping-like object (e.g., Django form instance),
    returning None if missing or on error."""
    if d is None:
        return None
    try:
        if hasattr(d, 'get'):
            return d.get(key)
        return d[key]
    except (KeyError, AttributeError, TypeError):
        return None
