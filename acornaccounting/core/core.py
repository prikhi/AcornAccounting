import datetime

from .forms import DateRangeForm


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
    """Set the start_date to the first of the year if form is unbound."""
    if not form.is_bound:
        form.initial['start_date'] = first_day_of_year()
        start_date = datetime.date(datetime.date.today().year, 1, 1)
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
