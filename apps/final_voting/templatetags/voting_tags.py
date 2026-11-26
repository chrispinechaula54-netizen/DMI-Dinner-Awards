from django import template

register = template.Library()

@register.filter
def get_item(mapping, key):
    return mapping.get(key)


@register.filter
def voting_initials(value):
    def person_initials(person):
        words = person.strip().split()
        if not words:
            return '?'
        return (words[0][0] + (words[-1][0] if len(words) > 1 else '')).upper()

    pair = [part.strip() for part in value.split(' and ', 1)]
    return ' · '.join(person_initials(person) for person in pair)
