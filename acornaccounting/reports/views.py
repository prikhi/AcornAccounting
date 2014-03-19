import datetime

from django.shortcuts import render

from accounts.models import Account, Header
from core.core import first_day_of_year, process_date_range_form
from events.models import Event, HistoricalEvent


def events_report(request, template_name="reports/events.html"):
    """Display all :class:`Events<events.models.Event>`.

    :param template_name: The template file to use to render the response.
    :type template_name: str
    :returns: HTTP Response with an ``events`` context variable.
    :rtype: HttpResponse

    """
    events = Event.objects.all()
    historical_events = HistoricalEvent.objects.all()
    return render(request, template_name, locals())


def profit_loss_report(request, template_name="reports/profit_loss.html"):
    """
    Display the Profit or Loss for a time period calculated using all Income
    and Expense :class:`Accounts<accounts.models.Account>`.

    The available ``GET`` parameters are ``start_date`` and ``stop_date``. They
    control the date range used for the calculations.

    This view is used to show the Total, Header and Account Net Changes over
    a specified date range. It uses the Net Changes to calculate various Profit
    amounts, passing them as context variables:

    * ``gross_profit``: Income - Cost of Goods Sold
    * ``operating_profit``: Gross Profit - Expenses
    * ``net_profit``: Operating Profit + Other Income - Other Expenses

    Also included is the ``headers`` dictionary which contains the ``income``,
    ``cost_of_goods_sold``, ``expenses``, ``other_income``, and
    ``other_expense`` keys. These keys point to the root node for the
    respective :attr:~accounts.models.BaseAccountModel.type`.

    These nodes have additional attributes appended to them, ``total``,
    ``accounts`` and ``descendants``. ``total`` represents the total Net Change
    for the node.  ``accounts`` and ``descendants`` are lists of child
    nodes(also with a ``total`` attribute).

    :param template_name: The template file to use to render the response.
    :type template_name: str
    :returns: HTTP Response with the start/stop dates, ``headers`` dictionary
              and Profit Totals
    :rtype: HttpResponse

    """
    form, start_date, stop_date = process_date_range_form(request)
    form, start_date = _set_start_date_to_first_of_year(form, start_date)
    headers_and_types = _get_profit_loss_header_keys_and_types()
    headers = {
        header_key: _get_profit_loss_header_totals(
            header_type, start_date, stop_date)
        for (header_key, header_type) in headers_and_types}
    gross_profit, operating_profit, net_profit = _get_profit_totals(headers)
    return render(request, template_name, locals())


def _get_profit_loss_header_keys_and_types():
    """Return a tuple of tuples containing a root header key and it's type."""
    return (('income', 4),
            ('cost_of_goods_sold', 5),
            ('expenses', 6),
            ('other_income', 7),
            ('other_expenses', 8))


def _get_profit_loss_header_totals(header_type, start_date, stop_date):
    """
    Return a root Header with the `descendants`, `accounts` and `total`
    attributes.

    The `descendants` attribute is a list of direct descendants, with their own
    `total` and `descendants` attributes.

    The `total` attribute should represent the net change of the Header or
    Account over the specified `start_date` and `stop_date`.

    """
    root_header = Header.objects.get(parent=None, type=header_type)
    return _get_profit_loss_header(root_header, start_date, stop_date)


def _get_profit_loss_header(header, start_date, stop_date):
    """
    Return the `header` instance with additional attributes of accounts,
    descendants and total change for the time period.

    """
    header.accounts = [
        _get_profit_loss_account(account, start_date, stop_date)
        for account in header.account_set.all()
    ]
    if header.level < 2:
        header.descendants = [
            _get_profit_loss_header(child, start_date, stop_date)
            for child in header.get_children()]
        header.total = (sum(account.total for account in header.accounts) +
                        sum(child.total for child in header.descendants))
    else:
        descendants = header.get_descendants(include_self=True)
        accounts = [_get_profit_loss_account(account, start_date, stop_date)
                    for descendant in descendants
                    for account in descendant.account_set.all()]
        header.total = sum(account.total for account in accounts)
    return header


def _get_profit_loss_account(account, start_date, stop_date):
    """
    Return the `account` instance with an additional `total` attribute,
    containing the net change for the time period.

    """
    in_range_transactions = account.transaction_set.filter(
        date__lte=stop_date, date__gte=start_date)
    _, _, net_change = in_range_transactions.get_totals(net_change=True)
    if account.flip_balance():
        net_change *= -1
    account.total = net_change
    return account


def _get_profit_totals(headers):
    """Calculate and return the Gross, Operating and Net Profits."""
    gross_profit = (headers['income'].total -
                    headers['cost_of_goods_sold'].total)
    operating_profit = gross_profit - headers['expenses'].total
    net_profit = (operating_profit + headers['other_income'].total -
                  headers['other_expenses'].total)
    return (gross_profit, operating_profit, net_profit)


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
    form, start_date = _set_start_date_to_first_of_year(form, start_date)
    accounts = [_get_account_details(x, start_date, stop_date) for x in
                list(Account.objects.all().order_by('full_number'))]

    return render(request, template_name, {'start_date': start_date,
                                           'stop_date': stop_date,
                                           'accounts': accounts,
                                           'form': form})


def _set_start_date_to_first_of_year(form, start_date):
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
