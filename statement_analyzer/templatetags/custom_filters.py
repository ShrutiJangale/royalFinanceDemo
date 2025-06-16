from django import template

register = template.Library()

@register.filter
def replace_underscores_with_spaces(value):
    """Replaces underscores with spaces in a string."""
    if isinstance(value, str):
        return value.replace('_', ' ')
    return value