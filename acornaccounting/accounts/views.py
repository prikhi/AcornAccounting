import datetime

from dateutil import relativedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.db.models import Q, Max
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render, get_object_or_404


from core.core import (today_in_american_format,
                       process_month_start_date_range_form,
                       process_year_start_date_range_form)
from fiscalyears.fiscalyears import get_start_of_current_fiscal_year

from .forms import AccountReconcileForm, ReconcileTransactionFormSet
from .models import Account, Header, HistoricalAccount


def quick_account_search(request):
    """Processes search for quick_account tag"""
    if 'account' in request.GET:
        account = get_object_or_404(Account, pk=request.GET.get('account'))
        return HttpResponseRedirect(reverse('show_account_detail',
                                            args=[account.slug]))
    else:
        raise Http404


def quick_bank_search(request):
    """Processes search for bank journals"""
    if 'bank' in request.GET:
        account = get_object_or_404(Account, pk=request.GET.get('bank'),
                                    bank=True)
        return HttpResponseRedirect(reverse('bank_journal',
                                            kwargs={'account_slug':
                                                    account.slug}))
    else:
        raise Http404


def show_accounts_chart(request, header_slug=None,
                        template_name="accounts/account_charts.html"):
    """Retrieves self and descendant Headers or all Headers"""
    if header_slug:
        header = get_object_or_404(Header, slug=header_slug)
        root_nodes = [header]
    else:
        root_nodes = Header.objects.filter(parent=None).order_by('type')
    for root_node in root_nodes:
        root_node.descendants = root_node.get_descendants(include_self=True)
    return render(request, template_name, locals())


def show_account_detail(request, account_slug,
                        template_name="accounts/account_detail.html"):
    """
    Displays a list of :class:`Transaction` instances for the :class:`Account`
    with a :attr:`~Account.slug` equal to the ``account_slug`` parameter.

    The following ``GET`` parameters are accessible:
        * ``start_date`` - The starting date to filter the returned
          :class:`Transactions<Transaction>` by.
        * ``stop_date`` - The ending date to filter the returned
          :class:`Transactions<Transaction>` by.

    The ``start_date`` and ``stop_date`` variables default to the first day of
    the month and the current date.

    The view will provide ``start_balance``, ``end_balance``, ``transactions``,
    ``debit_total``, ``credit_total`` and ``net_change`` context variables. The
    :class:`Transactions<Transaction>` in the context variable ``transactions``
    will have the running balance added to the instance through the
    ``final_balance`` attribute.

    If the provided ``start_date`` is before the start of the current
    :class:`~fiscalyears.models.FiscalYear`, the running balance and
    :class:`Transaction's<entries.models.Transaction>` ``final_balance`` will
    not be calculated.

    If there are no :class:`Transactions<entries.models.Transaction>` the
    ``start_balance`` and ``end_balance`` will both be set to the balance on
    the ``start_date``

    :param account_slug: The :attr:`~accounts.models.Account.slug` of top   \
            :class:`Account` to retrieve.
    :type account_slug: str
    :param template_name: The template file to use to render the response.
    :type template_name: str
    :returns: HTTP Response with :class:`Transactions<Transaction>` and     \
            balance counters.
    :rtype: HttpResponse
    """
    form, start_date, stop_date = process_year_start_date_range_form(request)
    account = get_object_or_404(Account, slug=account_slug)
    date_range_query = (Q(date__lte=stop_date) & Q(date__gte=start_date))
    debit_total, credit_total, net_change = account.transaction_set.filter(
        date_range_query).get_totals(net_change=True)
    transactions = account.transaction_set.filter(
        date_range_query).select_related('journal_entry', 'bankspendingentry',
                                         'bankspend_entry',
                                         'bankreceivingentry',
                                         'bankreceive_entry')
    current_fiscal_start_date = get_start_of_current_fiscal_year()
    show_balance = (current_fiscal_start_date is None or
                    current_fiscal_start_date <= start_date)
    if not show_balance:
        messages.info(request, "The Balance counters are only available when "
                      "the Start Date is in the current Fiscal Year (after "
                      "{0})".format(current_fiscal_start_date.strftime(
                          "%m/%d/%Y")))
    if transactions.exists() and show_balance:
        start_balance = transactions[0].get_initial_account_balance()
        end_balance = start_balance
        # TODO: Use .get_totals() instead of looping through each
        for transaction in transactions:
            if account.flip_balance():
                end_balance -= transaction.balance_delta
            else:
                end_balance += transaction.balance_delta
            transaction.final_balance = end_balance
    else:
        start_balance = end_balance = account.get_balance_by_date(start_date)
    return render(request, template_name, locals())


def show_account_history(request, month=None, year=None,
                         template_name="accounts/account_history.html"):
    """
    Displays a list of :class:`~accounts.models.HistoricalAccount` instances,
    grouped by the optional ``month`` and ``year``.

    By default a list of the instances from this month of last year will be
    returned. If those instances do not exist, the most recent month/year list
    will be displayed.

    If no instances of :class:`accounts.models.HistoricalAccount` exist, an
    empty string will be returned.

    The following ``GET`` parameters are accessible:
        * ``next`` - Use the next month relative to the passed ``month`` and
          ``year`` values. Redirects back to passed ``month`` and ``year`` if
          no Historical Accounts exist.
        * ``previous`` - Use the previous month relative to the passed
          ``month`` and ``year`` values. Redirects back to passed ``month``
          and ``year`` if no Historical Accounts exist.

    :param month: The Month to select, usage requires a specified year.
    :type month: int
    :param year: The Year to select, usage requires a specified month.
    :type year: int
    :param template_name: The template to use.
    :type template_name: string
    :returns: HTTP context with a list of instances or empty string as \
              ``accounts`` and a :class:`~datetime.date` as ``date``
    :rtype: HttpResponse
    :raises Http404: if an invalid ``month`` or ``year`` is specified.
    """
    # TODO: Display "No Account History For This Date." Instead of redirecting
    # or disable the next/previous buttons if there are none
    if 'next' in request.GET:
        datemod = datetime.timedelta(days=31)
    elif 'previous' in request.GET:
        datemod = datetime.timedelta(days=-1)
    else:
        datemod = datetime.timedelta(0)

    if month is None and year is None:
        today = datetime.date.today()
        last_year = today.year - 1
        this_month_last_year = datetime.date(last_year, today.month, 1)
        accounts = HistoricalAccount.objects.filter(date=this_month_last_year)
        max_date = HistoricalAccount.objects.aggregate(
            Max('date')).get('date__max')
        if accounts.exists():
            month = today.month
            year = today.year - 1
        elif max_date is not None:
            month = max_date.month
            year = max_date.year
        else:
            # TODO: No Account History Exists
            return render(request, template_name, {'accounts': ''})

    try:
        date = datetime.date(day=1, month=int(month), year=int(year)) + datemod
    except ValueError:
        raise Http404
    accounts = HistoricalAccount.objects.filter(date__month=date.month,
                                                date__year=date.year)

    next_month = date + relativedelta.relativedelta(months=1)
    previous_month = date - relativedelta.relativedelta(months=1)
    has_next = HistoricalAccount.objects.filter(
        date__month=next_month.month,
        date__year=next_month.year).exists()
    has_previous = HistoricalAccount.objects.filter(
        date__month=previous_month.month,
        date__year=previous_month.year).exists()

    date_change = bool('next' in request.GET or 'previous' in request.GET)
    exists = accounts.exists()

    if date_change and exists:
        return HttpResponseRedirect(
            reverse('accounts.views.show_account_history',
                    kwargs={'month': date.month, 'year': date.year}))
    elif exists:
        return render(request, template_name,
                      {'accounts': accounts, 'date': date,
                       'has_next': has_next, 'has_previous': has_previous})
    elif date_change:
        return HttpResponseRedirect(
            reverse('accounts.views.show_account_history',
                    kwargs={'month': month, 'year': year}))
    else:
        # TODO: No Account History Exists
        return render(request, template_name, {'accounts': '', 'date': date})


def bank_journal(request, account_slug,
                 template_name="accounts/bank_journal.html"):
    form, start_date, stop_date = process_month_start_date_range_form(request)
    account = get_object_or_404(Account, slug=account_slug, bank=True)
    # TODO: Refactor into Account method, get_bank_transactions_by_date()
    in_range_bank_query = ((Q(bankspendingentry__isnull=False) |
                            Q(bankreceivingentry__isnull=False)) &
                           (Q(date__lte=stop_date) & Q(date__gte=start_date)))
    transactions = account.transaction_set.filter(
        in_range_bank_query).select_related('journal_entry',
                                            'bankspendingentry',
                                            'bankspend_entry',
                                            'bankreceivingentry',
                                            'bankreceive_entry')
    return render(request, template_name, locals())


@login_required
def reconcile_account(request, account_slug,
                      template_name="accounts/account_reconcile.html"):
    """Reconcile an Account against a Statement.

    This view presents a form to the user, allowing them to enter a ``Statement
    Balance`` and ``Statement Date``. Upon a ``GET`` request with valid data,
    the view will display all unreconciled :class:`Transactions<Transaction>`
    from before the entered ``Statement Date``.

    The user will then select which :class:`Transactions<Transaction>` to
    reconcile. If a balanced form is submit, the view will mark each
    marked :class:`Transaction` as reconciled. The user will then be redirected
    to the :class:`Account's<Account>` :func:`show_account_detail` view.

    :param account_slug: The slug of the :class:`Account` to reconcile.
    :type account_slug: str
    :param template_name: The template to use.
    :type template_name: str
    :returns: HTTP response containing :class:`AccountReconcileForm`,   \
            :class:`~accounts.forms.ReconcileTransactionFormSet`, the   \
            :class:`Account`, and the Reconciled Balance and Last       \
            Reconciled Date as context. Redirects if successful POST is sent.
    :rtype: HttpResponse or HttpResponseRedirect
    """
    account = get_object_or_404(Account, slug=account_slug)
    last_reconciled = account.last_reconciled
    reconciled_balance = account.reconciled_balance
    if request.method == 'POST':
        if request.POST.get('submit') == 'Get Transactions':
            account_form = AccountReconcileForm(request.POST,
                                                prefix='account',
                                                instance=account)
            if account_form.is_valid():
                stop_date = account_form.cleaned_data.get('statement_date')
                pre_statement_transactions = account.transaction_set.filter(
                    reconciled=False).filter(date__lte=stop_date)
                transaction_formset = ReconcileTransactionFormSet(
                    queryset=pre_statement_transactions)
                reconciled_balance *= (-1 if account.flip_balance() else 1)
                return render(request, template_name,
                              {'account': account,
                               'reconciled_balance': reconciled_balance,
                               'last_reconciled': last_reconciled,
                               'account_form': account_form,
                               'transaction_formset': transaction_formset})
        elif request.POST.get('submit') == 'Reconcile Transactions':
            account_form = AccountReconcileForm(request.POST,
                                                prefix='account',
                                                instance=account)
            transaction_formset = ReconcileTransactionFormSet(request.POST)
            if account_form.is_valid():
                transaction_formset.reconciled_balance = reconciled_balance
                transaction_formset.account_form = account_form
                # Flip the reconciled balance for display in case of formset
                # error
                reconciled_balance *= (-1 if account.flip_balance() else 1)
                if transaction_formset.is_valid():
                    transaction_formset.save()
                    account.last_reconciled = account_form.cleaned_data.get(
                        'statement_date')
                    account.reconciled_balance = account_form.cleaned_data.get(
                        'statement_balance')
                    account.save()
                    messages.success(request, "The account was reconciled.")
                    return HttpResponseRedirect(
                        reverse('accounts.views.show_account_detail',
                                kwargs={'account_slug': account.slug}))
        else:
            raise Http404
    else:
        reconciled_balance *= (-1 if account.flip_balance() else 1)
        account_form = AccountReconcileForm(
            prefix='account', instance=account,
            initial={'statement_date': today_in_american_format(),
                     'statement_balance': reconciled_balance})
    return render(request, template_name, locals())
