from django import template

from accounts.forms import QuickAccountForm, QuickBankForm

from core.core import process_quick_search_form

register = template.Library()


@register.inclusion_tag("tags/quick_search.html")
def quick_search(GET):
    account_form = process_quick_search_form(GET, 'account', QuickAccountForm)
    bank_form = process_quick_search_form(GET, 'bank', QuickBankForm)
    return {'quick_account_form': account_form[0],
            'quick_bank_form': bank_form[0]}


@register.inclusion_tag("tags/date_range_form.html")
def date_range_form(form):
    return {'form': form}


@register.inclusion_tag('tags/receipt_list.html')
def receipt_list(journal_entry, show_heading=True):
    """Render a Journal Entries Receipts in a <ul>."""
    return {'journal_entry': journal_entry,
            'show_heading': show_heading}
