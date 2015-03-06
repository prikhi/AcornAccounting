import datetime

from fiscalyears.fiscalyears import get_start_of_current_fiscal_year

from .forms import DateRangeForm


def remove_trailing_zeroes(number):
    """Reduce any trailing zeroes down to two decimal places.

    :param number: The number to reduce.
    :type number: A number or string representing a number.
    :returns: The number with zeroes past the 2nd decimal place removed.
    :rtype: String

    """
    number_string = str(float(number)).rstrip('0')
    decimal_places = len(number_string.split('.')[1])
    if decimal_places < 2:
        number_string += '0' * (2 - decimal_places)
    return number_string


def today_in_american_format():
    """Return the Today's Date in ``MM/DD/YYYY`` format."""
    return _american_format(datetime.date.today())


def first_day_of_month():
    """Return the first day of the current month in ``MM/DD/YYYY`` format."""
    today = datetime.date.today()
    return _american_format(datetime.date(today.year, today.month, 1))


def first_day_of_year():
    """Return the first day of the current year in ``MM/DD/YYYY`` format."""
    today = datetime.date.today()
    return _american_format(datetime.date(today.year, 1, 1))


def _american_format(date):
    """Return a string of the date in the American ``MM/DD/YY`` format."""
    return date.strftime('%m/%d/%Y')


def process_month_start_date_range_form(request):
    """
    Returns a :class:`~.forms.DateRangeForm`, ``start_date`` and ``stop_date``
    based on the request ``GET`` data.  Defaults to using beginning of this
    month to today.
    """
    form = DateRangeForm(initial={'start_date': first_day_of_month(),
                                  'stop_date': today_in_american_format()})
    stop_date = datetime.date.today()
    start_date = datetime.date(stop_date.year, stop_date.month, 1)
    if 'start_date' in request.GET and 'stop_date' in request.GET:
        form = DateRangeForm(request.GET)
        if form.is_valid():
            start_date = form.cleaned_data.get('start_date', start_date)
            stop_date = form.cleaned_data.get('stop_date', stop_date)
    return form, start_date, stop_date


def process_year_start_date_range_form(request):
    """
    Returns a :class:`~.forms.DateRangeForm`, ``start_date`` and ``stop_date``
    based on the request ``GET`` data.  Defaults to using beginning of this
    year to today.
    """
    form, start_date, stop_date = process_month_start_date_range_form(request)
    form, start_date = _set_start_date_to_first_of_year(form, start_date)
    return form, start_date, stop_date


def _set_start_date_to_first_of_year(form, start_date):
    """Set start_date to the start of the fiscal year if form is unbound."""
    if not form.is_bound:
        fiscal_start = get_start_of_current_fiscal_year()
        start_date = (fiscal_start if fiscal_start is not None else
                      datetime.date(datetime.date.today().year, 1, 1))
        form.initial['start_date'] = _american_format(start_date)
    return form, start_date


def process_quick_search_form(get_dictionary, get_variable, form):
    """Return a form and the id of the related model.

    QuickSearchForms are Forms with a single Select input filled with model
    instances. Each Search submits with a different ``GET`` variable.

    This function determines if the ``get_variable`` is in the ``request``'s
    ``GET`` data. If so, and the Form is valid, it will bind the form and
    return a tuple containing the bound form and the ``id`` of the selected
    object. Otherwise, the function will return tuple containing an unbound
    form and :obj:`None`.

    For usage, see :func:`core.templatetags.core_tags`.

    :param get_dictionary: The request's ``GET`` dictionary.
    :param get_variable: The ``GET`` variable to search the request for, it's
                         presence indicates form submission.
    :type get_variable: str
    :param form: The form class to use.
    :type form: :class:`~django.forms.Form`
    :returns: A tuple containing a bound or unbound Form and the objects ``id``
    :rtype: :obj:`tuple`

    """
    object_id = None
    form_was_submit = get_variable in get_dictionary
    if form_was_submit:
        form_instance = form(get_dictionary)
        if form_instance.is_valid():
            object_id = form.cleaned_data.get(get_variable)
    else:
        form_instance = form()
    return form_instance, object_id
