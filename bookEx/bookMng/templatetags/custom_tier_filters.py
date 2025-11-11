from django import template

register = template.Library()

tier_order = {
    'Free': 0,
    'Bronze': 1,
    'Silver': 2,
    'Silver+': 3,
    'Gold': 4,
    'GoldOnly': 5,
}

@register.filter
def tier_value(tier):
    return tier_order.get(tier, -1)

@register.simple_tag
def is_tier_lower(user_tier, book_tier):
    return tier_order.get(user_tier, -1) < tier_order.get(book_tier, -1)