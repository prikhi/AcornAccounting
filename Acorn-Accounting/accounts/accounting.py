"""
General Functions for Accounting App
"""
import datetime

from .forms import (DateRangeForm, QuickAccountForm, QuickBankForm,
                    QuickEventForm)


def american_today():
    return datetime.date.today().strftime('%m/%d/%Y')


def first_of_month():
    today = datetime.date.today()
    return datetime.date(today.year, today.month, 1).strftime('%m/%d/%Y')


# TODO: Refactor the 3 following functions into a single function that:
#   Takes a form, request and get variable
#   Returns either a new or bound form
def process_quick_account_form(GET):
    """
    Returns a quick account dropdown select form and an Account id
    """
    form = QuickAccountForm()
    account_id = None
    if 'account' in GET:
        form = QuickAccountForm(GET)
        if form.is_valid():
            account_id = form.cleaned_data['account']
    return form, account_id


def process_quick_bank_form(GET):
    """
    Returns a quick bank journal dropdown select form and an Account id
    """
    form = QuickBankForm()
    account_id = None
    if 'bank' in GET:
        form = QuickBankForm(GET)
        if form.is_valid():
            account_id = form.cleaned_data['bank']
    return form, account_id


def process_quick_event_form(GET):
    """
    Returns a quick event dropdown select form and an Event id
    """
    form = QuickEventForm()
    event_id = None
    if 'event' in GET:
        form = QuickBankForm(GET)
        if form.is_valid():
            event_id = form.cleaned_data.get('event')
    return form, event_id


def process_date_range_form(request):
    """
    Returns a date range form, startdate and stopdate based on the request GET.
    Defaults to using beginning of this month to today.
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
