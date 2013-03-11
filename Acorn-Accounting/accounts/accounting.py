'''
    General Functions for Accounting App
'''
import datetime

from .forms import DateRangeForm
from accounts.forms import QuickAccountForm


def process_quick_search_form(request):
    '''
    Returns a quick account dropdown select form and an Account id
    '''
    form = QuickAccountForm()
    account_id = None
    if 'account' in request:
        form = QuickAccountForm(request)
        if form.is_valid():
            account_id = form.cleaned_data['account']
    return form, account_id


def process_date_range_form(request):
    '''
    Returns a date range form, startdate and stopdate based on the request GET.
    Defaults to using beginning of this month to today.
    '''
    form = DateRangeForm()
    stopdate = datetime.date.today()
    startdate = datetime.date(stopdate.year, stopdate.month, 1)
    if 'startdate' in request.GET and 'stopdate' in request.GET:
        form = DateRangeForm(request.GET)
        if form.is_valid():
            startdate = form.cleaned_data['startdate']
            stopdate = form.cleaned_data['stopdate']
    return form, startdate, stopdate
