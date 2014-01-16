import datetime

from .forms import DateRangeForm


def american_today():
    """Return the current Date in ``MM/DD/YYYY`` format."""
    return datetime.date.today().strftime('%m/%d/%Y')


def first_of_month():
    """Return the first day of the current month."""
    today = datetime.date.today()
    return datetime.date(today.year, today.month, 1).strftime('%m/%d/%Y')


def process_date_range_form(request):
    """
    Returns a :class:`~.forms.DateRangeForm`, ``startdate`` and ``stopdate``
    based on the request ``GET`` data.  Defaults to using beginning of this
    month to today.
    """
    form = DateRangeForm(initial={'startdate': first_of_month(),
                                  'stopdate': american_today()})
    stopdate = datetime.date.today()
    startdate = datetime.date(stopdate.year, stopdate.month, 1)
    if 'startdate' in request.GET and 'stopdate' in request.GET:
        form = DateRangeForm(request.GET)
        if form.is_valid():
            startdate = form.cleaned_data.get('startdate', startdate)
            stopdate = form.cleaned_data.get('stopdate', stopdate)
    return form, startdate, stopdate


def process_quick_search_form(get_dictionary, get_variable, form):
    """Return a form and the id of the related model.

    QuickSearchForms are Forms with a single Select input filled with model
    instances. Each Search submits with a different ``GET`` variable.

    This function determines if the ``get_variable`` is in the ``request``'s
    ``GET`` data. If so, and the Form is valid, it will bind the form and
    return a tuple containing the bound form and the ``id`` of the selected
    object. Otherwise, the function will return tuple containing an unbound
    form and :obj:`None`.

    :param get_dictionary: The request's ``GET`` dictionary.
    :param get_variable: The ``GET`` variable to search the request for, it's
                         presence indicates form submission.
    :type get_variable: str
    :param form: The form class to use.
    :type form: :class:`~django.forms.Form`
    :returns: A tuple containing a bound or unbound Form and the objects ``id``
    :rtype: :obj:`tuple`

    """
    form = form()
    object_id = None
    if get_variable in get_dictionary:
        form = form(get_dictionary)
        if form.is_valid():
            object_id = form.cleaned_data.get(get_variable)
    return form, object_id
