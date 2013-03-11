from django import template

from ..accounting import process_quick_search_form


register = template.Library()


@register.inclusion_tag("tags/quick_search.html")
def quick_account(request):
    form, account_id = process_quick_search_form(request)
    return {'quick_account_form': form}
