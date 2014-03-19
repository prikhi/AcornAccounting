import calendar
import datetime

from dateutil import rrule
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.db.models import Sum
from django.http import HttpResponseRedirect
from django.shortcuts import render

from accounts.models import Account, HistoricalAccount
from entries.models import (Transaction, JournalEntry, BankSpendingEntry,
                            BankReceivingEntry)
from events.models import Event, HistoricalEvent


from .fiscalyears import get_start_of_current_fiscal_year
from .forms import FiscalYearForm, FiscalYearAccountsFormSet
from .models import FiscalYear


@login_required
def add_fiscal_year(request, template_name="fiscalyears/year_add.html"):
    """
    Creates a new :class:`~.models.FiscalYear` using a
    :class:`~.forms.FiscalYearForm` and
    :data:`~.forms.FiscalYearAccountsFormSet`.

    Starting a new :class:`~.models.FiscalYear` involves the following
    procedure:

         1. Setting a ``period`` and Ending ``month`` and ``year`` for the New
            Fiscal Year.
         2. Selecting Accounts to exclude from purging of unreconciled
            :class:`Transactions<entries.models.Transaction>`.
         3. Create a :class:`~accounts.models.HistoricalAccount` for every
            :class:`~accounts.models.Account` and month in the previous
            :class:`~.models.FiscalYear`, using ending balances for Asset,
            Liability and Equity :class:`Accounts<accounts.models.Account>` and
            balance changes for the others.
         4. Delete all :class:`Journal Entries<entries.models.JournalEntry>`,
            except those with unreconciled
            :class:`Transactions<entries.models.Transaction>` with
            :class:`Accounts<accounts.models.Account>` in the exclude lists.
         5. Move the ``balance`` of the ``Current Year Earnings``
            :class:`~accounts.models.Account` into the ``Retained Earnings``
            :class:`~accounts.models.Account`.
         6. Zero the ``balance`` of all Income, Cost of Sales, Expense, Other
            Income and Other Expense
            :class:`Accounts<accounts.models.Account>`.

    :param template_name: The template to use.
    :type template_name: string
    :returns: HTTP response containing
            :class:`~.forms.FiscalYearForm` and
            :data:`~.forms.FiscalYearAccountsFormSet` as context.
            Redirects if successful POST is sent.
    :rtype: HttpResponse or HttpResponseRedirect

    """
    previous_year = _get_previous_year_if_exists()

    if request.method == 'POST':
        fiscal_year_form = FiscalYearForm(request.POST)
        accounts_formset = FiscalYearAccountsFormSet(request.POST)
        valid = fiscal_year_form.is_valid() and accounts_formset.is_valid()
        if valid and previous_year:
            start_of_previous_year = get_start_of_current_fiscal_year()
            end_of_previous_year = _get_last_day_of_month(previous_year.date)

            [_archive_and_delete_event(event) for event in
             Event.objects.filter(date__lte=end_of_previous_year)]

            months_in_previous_year = _get_months_in_range(
                start_of_previous_year, end_of_previous_year)
            for month in months_in_previous_year:
                last_day_of_month = _get_last_day_of_month(month)
                HistoricalAccount.objects.bulk_create(
                    [_build_historical_account(account, last_day_of_month) for
                     account in Account.objects.all()]
                )

            excluded_transactions = _get_excluded_transactions(
                accounts_formset)

            journals = [Journal.objects.filter(date__lte=end_of_previous_year)
                        for Journal in (JournalEntry, BankReceivingEntry,
                                        BankSpendingEntry)]
            for entries in journals:
                for entry in entries:
                    _delete_entry_if_not_excluded(entry, excluded_transactions)
            [_correct_account_balance(account, end_of_previous_year) for
             account in Account.objects.all()]

            _transfer_current_year_earnings(end_of_previous_year)

            fiscal_year_form.save()
            messages.success(request, "Your previous fiscal year has been "
                             "closed and a new fiscal year has been started.")
            return HttpResponseRedirect(reverse(
                'accounts.views.show_accounts_chart'))
        elif valid:
            fiscal_year_form.save()
            messages.success(request, "A new fiscal year has been started.")
            return HttpResponseRedirect(reverse(
                'accounts.views.show_accounts_chart'))
    else:
        fiscal_year_form = FiscalYearForm()
        accounts_formset = FiscalYearAccountsFormSet(
            queryset=Account.objects.order_by('last_reconciled',
                                              'full_number'))
    return render(request, template_name, locals())


def _get_previous_year_if_exists():
    """Return the last FiscalYear or False if none exists."""
    try:
        previous_year = FiscalYear.objects.latest()
    except FiscalYear.DoesNotExist:
        previous_year = False
    return previous_year


def _archive_and_delete_event(event):
    """Create a HistoricalEvent and delete the Event."""
    debit_total, credit_total, net_change = event.transaction_set.get_totals(
        net_change=True)

    HistoricalEvent.objects.create(
        name=event.name, number=event.number, date=event.date, city=event.city,
        state=event.state, debit_total=debit_total, credit_total=credit_total,
        net_change=net_change)
    event.delete()


def _get_months_in_range(start_date, stop_date):
    """Return a list of datetime.date months between the start & stop dates."""
    return rrule.rrule(rrule.MONTHLY, dtstart=start_date, until=stop_date)


def _build_historical_account(account, month):
    """Create a HistoricalAccount for the specified account and month."""
    if account.type in (1, 2, 3):
        amount = account.get_balance_by_date(date=month)
    else:
        amount = account.get_balance_change_by_month(month)

    if account.flip_balance():      # Flip back to credit/debit
        amount *= -1                # amount from value amount

    historical_account = HistoricalAccount(
        account=account, date=month, name=account.name, type=account.type,
        number=account.get_full_number(), amount=amount)
    return historical_account


def _get_excluded_transactions(accounts_formset):
    """
    Process a FiscalYearAccountsFormSet and return a set of excluded
    Transactions.

    """
    excluded_accounts = [form.instance for form in accounts_formset if
                         form.cleaned_data.get('exclude')]
    excluded_transactions = frozenset(Transaction.objects.filter(
        account__in=excluded_accounts, reconciled=False))
    return excluded_transactions


def _get_last_day_of_month(month):
    """Return the last day of the specified month."""
    last_day_of_month = month.replace(
        day=calendar.monthrange(month.year, month.month)[1])
    return last_day_of_month


def _get_all_transactions(entry):
    """Get all Transactions of the Entry, including a main_transaction."""
    entry_transactions = list(entry.transaction_set.all())
    if hasattr(entry, 'main_transaction'):
        entry_transactions.append(entry.main_transaction)
    return entry_transactions


def _delete_entry_if_not_excluded(entry, excluded_transactions):
    """Delete an Entry if none of it's Transactions are excluded."""
    entry_transactions = _get_all_transactions(entry)
    entry_is_not_excluded = excluded_transactions.isdisjoint(
        entry_transactions)
    if entry_is_not_excluded:
        [transaction.delete() for transaction in entry_transactions]
        entry.delete()


def _correct_account_balance(account, historical_year_end):
    """
    Set the Account balance to the latest HistoricalAccount balance plus any
    Transactions after the end of the last Fiscal Year.

    """
    new_year_sum = account.transaction_set.filter(
        date__gt=historical_year_end).aggregate(Sum('balance_delta'))
    account.balance = new_year_sum.get('balance_delta__sum') or 0
    if account.type in (1, 2, 3):
        hist_acct = account.historicalaccount_set.latest()
        account.balance += hist_acct.amount
    account.save()


def _transfer_current_year_earnings(entry_date):
    """Transfer the Current Year Earnings balance into Retained Earnings."""
    current_earnings = Account.objects.get(name='Current Year Earnings')
    retained_earnings = Account.objects.get(name='Retained Earnings')
    historical_current = current_earnings.historicalaccount_set.latest()
    transfer_date = entry_date + datetime.timedelta(days=1)

    entry = JournalEntry.objects.create(date=transfer_date,
                                        memo='End of Fiscal Year Adjustment')
    Transaction.objects.create(journal_entry=entry, account=current_earnings,
                               balance_delta=historical_current.amount * -1)
    Transaction.objects.create(journal_entry=entry, account=retained_earnings,
                               balance_delta=historical_current.amount)
