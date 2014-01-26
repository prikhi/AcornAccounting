import datetime

from django.shortcuts import render

from accounts.models import Account
from core.core import first_day_of_year, process_date_range_form
from events.models import Event


def events_report(request, template_name="reports/events.html"):
    """Display all :class:`Events<events.models.Event>`."""
    events = Event.objects.all()
    return render(request, template_name, {'events': events})


def trial_balance_report(request, template_name="reports/trial_balance.html"):
    """
    Display the state and change of all :class:`Accounts
    <accounts.models.Account>` over a time period.

    The available ``GET`` parameters are ``start_date`` and ``stop_date``.

    The view also provides the ``start_date``, ``stop_date`` and ``accounts``
    context variables.

    The ``start_date`` and ``stop_date`` variables default to the first day of
    the year and the current date.

    The ``accounts`` variable is a list of dictionaries, each representing an
    :class:`~accounts.models.Account`. Each dictionary contains the
    :class:`Account's<accounts.models.Account>` number, name, balance at the
    beginning and end of the date range, total debits and credits and the net
    change.

    :param template_name: The template file to use to render the response.
    :type template_name: str
    :returns: HTTP Response with start and stop dates and an ``accounts`` list.
    :rtype: HttpResponse
    """
    form, start_date, stop_date = process_date_range_form(request)
    form, start_date = _set_start_date(form, start_date)
    accounts = [_get_account_details(x, start_date, stop_date) for x in
                list(Account.objects.all().order_by('full_number'))]

    return render(request, template_name, {'start_date': start_date,
                                           'stop_date': stop_date,
                                           'accounts': accounts,
                                           'form': form})


def _set_start_date(form, start_date):
    """Set the start_date to the first of the year if form is unbound."""
    if not form.is_bound:
        form.initial['start_date'] = first_day_of_year()
        start_date = datetime.date(datetime.date.today().year, 1, 1)
    return form, start_date


def _get_account_details(account, start_date, stop_date):
    """
    Return the Name, Number, URL, Starting/Ending Balances, Net Change and
    Credit/Debit Totals of an :class:`~accounts.models.Account` in the
    specified range.

    :param account: The Account whose details should be retrieved.
    :type account: :class:`~accounts.models.Account`
    :param start_date: The date representing the first day of the time period.
    :type start_date: :class:`datetime.date`
    :param stop_date: The date representing the last day of the time period.
    :type stop_date: :class:`datetime.date`
    :returns: Account details and activity information
    :rtype: dict
    """
    one_day = datetime.timedelta(days=1)
    start_balance = account.get_balance_by_date(start_date - one_day)
    end_balance = account.get_balance_by_date(stop_date)

    in_range_transactions = account.transaction_set.filter(
        date__gte=start_date, date__lte=stop_date)
    debit_total, credit_total, net_change = in_range_transactions.get_totals(
        net_change=True)

    return {'name': account.name,
            'number': account.get_full_number(),
            'beginning_balance': start_balance,
            'total_debits': debit_total,
            'total_credits': credit_total,
            'net_change': net_change,
            'ending_balance': end_balance,
            'url': account.get_absolute_url()}
