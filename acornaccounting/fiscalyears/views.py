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


from .fiscalyears import get_current_fiscal_year_start
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
    # TODO: Refactor this into FiscalYear.objects.get_latest_or_none()
    try:
        previous_year = FiscalYear.objects.latest()
    except FiscalYear.DoesNotExist:
        previous_year = False

    if request.method == 'POST':
        fiscal_year_form = FiscalYearForm(request.POST)
        accounts_formset = FiscalYearAccountsFormSet(request.POST)
        valid = fiscal_year_form.is_valid() and accounts_formset.is_valid()
        if valid and previous_year:
            # Create HistoricalAccounts
            stop_date = previous_year.date
            start_date = get_current_fiscal_year_start()
            # TODO: Refactor into FiscalYear.objects.current_years_months()
            for month in rrule.rrule(rrule.MONTHLY, dtstart=start_date,
                                     until=stop_date):
                last_day_of_month = month.replace(
                    day=calendar.monthrange(month.year, month.month)[1]
                ).date()
                # TODO: Use bulk_create() instead of creating and saving each
                # object, instantiate into a list or create a dictionary with
                # the data instead
                # Maybe use list comprehension + helper functions to generate
                # objects?
                for account in Account.objects.filter(type__in=(1, 2, 3)):
                    # Amount is end of month balance
                    amount = account.get_balance_by_date(
                        date=last_day_of_month)
                    if account.flip_balance():      # Flip back to credit/debit
                        amount *= -1                # amount from value amount
                    HistoricalAccount.objects.create(
                        account=account, date=month,
                        name=account.name, type=account.type,
                        number=account.get_full_number(),
                        amount=amount
                    )
                for account in Account.objects.filter(type__in=range(4, 9)):
                    # Amount is net change for month
                    amount = account.get_balance_change_by_month(month)
                    if account.flip_balance():      # Flip back to credit/debit
                        amount *= -1                # amount from value amount
                    HistoricalAccount.objects.create(
                        account=account, date=month,
                        name=account.name, type=account.type,
                        number=account.get_full_number(),
                        amount=amount
                    )
            # Create Transaction exclusion list
            # TODO: Make excluded_accounts a `set` then use set.intersection
            # to check for inclusion
            excluded_accounts = list()
            for form in accounts_formset:
                if form.cleaned_data.get('exclude'):
                    excluded_accounts.append(form.instance)
            excluded_transactions = Transaction.objects.filter(
                account__in=excluded_accounts, reconciled=False)
            # Purge Journal Entries
            historical_year_end = previous_year.date.replace(
                day=calendar.monthrange(previous_year.year,
                                        previous_year.end_month)[1])
            # TODO: turn into list comprehension + select related
            general = JournalEntry.objects.filter(
                date__lte=historical_year_end)
            receiving = BankReceivingEntry.objects.filter(
                date__lte=historical_year_end)
            spending = BankSpendingEntry.objects.filter(
                date__lte=historical_year_end)
            for entries in (general, receiving, spending):
                for entry in entries:
                    skip = False
                    # TODO: make transaction a `set` and check for inclusion
                    # using excluded_accounts.intersection
                    for transaction in entry.transaction_set.all():
                        if transaction in excluded_transactions:
                            skip = True
                            break
                    if (hasattr(entry, 'main_transaction') and
                            entry.main_transaction in excluded_transactions):
                        skip = True
                    if not skip:
                        entry.transaction_set.all().delete()
                        if hasattr(entry, 'main_transaction'):
                            entry.main_transaction.delete()
                        entry.delete()
            # Set new Account Balances
            # TODO: See if there is a way to do bulk updates for these
            for account in Account.objects.filter(type__in=(1, 2, 3)):
                # Balances will build upon last years
                hist_acct = account.historicalaccount_set.latest()
                new_year_sum = account.transaction_set.filter(
                    date__gt=historical_year_end
                ).aggregate(Sum('balance_delta'))
                account.balance = (new_year_sum.get('balance_delta__sum') or 0
                                   ) + hist_acct.amount
                account.save()
            for account in Account.objects.filter(type__in=range(4, 9)):
                # Balances will reflect Transactions in new Year
                new_year_sum = account.transaction_set.filter(
                    date__gt=historical_year_end).aggregate(
                        Sum('balance_delta'))
                account.balance = new_year_sum.get('balance_delta__sum') or 0
                account.save()
            # Move balance of Current Year Earnings to Retained Earnings
            # TODO: Refactor out into end_of_year_earnings_transfer()
            current_earnings = Account.objects.get(
                name='Current Year Earnings')
            retained_earnings = Account.objects.get(name='Retained Earnings')
            hist_current = current_earnings.historicalaccount_set.latest()
            transfer_date = historical_year_end + datetime.timedelta(days=1)
            entry = JournalEntry.objects.create(
                date=transfer_date, memo='End of Fiscal Year Adjustment')
            Transaction.objects.create(journal_entry=entry,
                                       account=current_earnings,
                                       balance_delta=hist_current.amount * -1)
            Transaction.objects.create(journal_entry=entry,
                                       account=retained_earnings,
                                       balance_delta=hist_current.amount)
            fiscal_year_form.save()
            messages.success(request, "A new fiscal year has been started.")
            return HttpResponseRedirect(reverse(
                'accounts.views.show_accounts_chart'))
        elif valid:
            fiscal_year_form.save()
            messages.success(request, "A new fiscal year has been started.")
            return HttpResponseRedirect(reverse(
                'accounts.views.show_accounts_chart'))
    else:
        fiscal_year_form = FiscalYearForm()
        accounts_formset = FiscalYearAccountsFormSet()
    return render(request, template_name, locals())
