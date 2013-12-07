from django import template

from ..accounting import process_quick_bank_form, \
    process_quick_account_form, process_quick_event_form


register = template.Library()


@register.inclusion_tag("tags/quick_search.html")
def quick_search(GET):
    account_form = process_quick_account_form(GET)
    bank_form = process_quick_bank_form(GET)
    event_form = process_quick_event_form(GET)
    return {'quick_account_form': account_form[0],
            'quick_bank_form': bank_form[0],
            'quick_event_form': event_form[0]}
