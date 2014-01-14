import locale
import re
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
    """Capitalize the first letter of each lowercase word."""
    output_list = list()
    uppercase_pattern = re.compile(r'[A-Z]')

    for word in str(value).split():
        uppercase_letter = uppercase_pattern.search(word)
        if uppercase_letter is None:
            word = string.capwords(str(word))
        output_list.append(word)

    output_string = ' '.join(output_list)

    return output_string
