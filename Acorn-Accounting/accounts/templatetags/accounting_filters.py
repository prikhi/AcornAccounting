import locale
import string

from django import template


register = template.Library()


@register.filter(name='currency')
def currency(value):
    try:
        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
    except:
        locale.setlocale(locale.LC_ALL, '')
    loc = locale.localeconv()

    value = locale.currency(value, loc['currency_symbol'], grouping=True)

    if '-' in value:
        return '(${0})'.format(value.replace('-$', ''))
    return value


@register.filter(name='int_to_tabs')
def tab_number(value):
    return u"\xa0" * 4 * int(value)


@register.filter(name="capwords")
def capitalize_words(value):
    return string.capwords(str(value))
