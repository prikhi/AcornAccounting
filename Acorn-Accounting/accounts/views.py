import calendar
import datetime
from dateutil import rrule

from django.db.models import Q, Sum, Max
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render_to_response, get_object_or_404
from django.template.context import RequestContext
from django.utils import timezone

from .accounting import american_today, process_date_range_form
from .forms import (JournalEntryForm, TransferFormSet, TransactionFormSet,
        BankSpendingForm, BankReceivingForm, BankReceivingTransactionFormSet,
        BankSpendingTransactionFormSet, AccountReconcileForm,
        ReconcileTransactionFormSet, FiscalYearForm, FiscalYearAccountsFormSet)
from .models import (Header, Account, JournalEntry, BankReceivingEntry,
        BankSpendingEntry, Transaction, Event, HistoricalAccount, FiscalYear)

# TODO: Globally - Replace render_to_response with render

# TODO: Use .get() for dictionary access

def quick_account_search(request):
    '''Processes search for quick_account tag'''
    if 'account' in request.GET:
        account = get_object_or_404(Account, pk=request.GET['account'])
        return HttpResponseRedirect(reverse('show_account_detail', args=[account.slug]))
    else:
        raise Http404


def quick_bank_search(request):
    '''Processes search for bank registers'''
    if 'bank' in request.GET:
        account = get_object_or_404(Account, pk=request.GET['bank'], bank=True)
        return HttpResponseRedirect(reverse('bank_register', kwargs={'account_slug': account.slug}))
    else:
        raise Http404


def quick_event_search(request):
    '''Processes search for events'''
    if 'event' in request.GET:
        event = get_object_or_404(Event, pk=request.GET['event'])
        return HttpResponseRedirect(reverse('show_event_detail', kwargs={'event_id': event.id}))
    else:
        raise Http404


def show_accounts_chart(request, header_slug=None, template_name="accounts/account_charts.html"):
    '''Retrieves self and descendant Headers or all Headers'''
    if header_slug:
        header = get_object_or_404(Header, slug=header_slug)
        nodes = header.get_descendants(include_self=True)
    else:
        nodes = Header.objects.all()

    return render_to_response(template_name,
                              locals(),
                              context_instance=RequestContext(request))


def show_account_detail(request, account_slug,
                        template_name="accounts/account_detail.html"):
    '''
    Displays a list of :class:`Transaction` instances for the :class:`Account`
    with a :attr:`~Account.slug` of :param:`account_slug`.

    The following ``GET`` parameters are accessible:
        * ``startdate`` - The starting date to filter the returned
          :class:`Transactions<Transaction>` by.
        * ``stopdate`` - The ending date to filter the returned
          :class:`Transactions<Transaction>` by.

    The ``startdate`` and ``stopdate`` variables default to the first day of
    the month and the current date.

    The view will provide ``startbalance``, ``endbalance``, ``transactions``,
    ``debit_total``, ``credit_total`` and ``net_change`` context variables. The
    :class:`Transactions<Transaction>` in the context variable ``transactions``
    will have the running balance added to the instance through the
    ``final_balance`` attribute.

    If the provided ``startdate`` is before the start of the current
    :class:`FiscalYear`, the running balance and
    :class:`Transaction's<Transaction>` ``final_balance`` will not be
    calculated.

    If there are no :class:`Transactions<Transaction>` the ``startbalance`` and
    ``endbalance`` will both be set to the balance on the ``startdate``

    :param account_slug: The :attr:`Account.slug` of the :class:`Account` to \
            retrieve.
    :type account_slug: string
    :param template_name: The template file to use to render the response.
    :type template_name:
    :returns: HTTP Response with :class:`Transactions<Transaction>` and \
            balance counters.
    :rtype: HttpResponse
    '''
    # TODO: Rename variables, startdate -> start_date, stopdate -> stop_date
    # fiscal_start -> current_fiscal_start_date, etc.
    form, startdate, stopdate = process_date_range_form(request)
    account = get_object_or_404(Account, slug=account_slug)
    query = (Q(date__lte=stopdate) & Q(date__gte=startdate))
    debit_total, credit_total, net_change = account.transaction_set.get_totals(query=query, net_change=True)
    transactions = account.transaction_set.filter(query)
    fiscal_start = FiscalYear.objects.current_start()
    show_balance = fiscal_start is None or fiscal_start <= startdate
    if transactions.exists() and show_balance:
        startbalance = transactions[0].get_initial_account_balance()
        endbalance = startbalance
        # TODO: Use .get_totals() instead of looping through each
        for transaction in transactions:
            if account.flip_balance():
                endbalance += -1 * transaction.balance_delta
            else:
                endbalance += transaction.balance_delta
            transaction.final_balance = endbalance
    else:
        startbalance = endbalance = account.get_balance_by_date(startdate)
    return render_to_response(template_name, locals(),
                              context_instance=RequestContext(request))


def show_account_history(request, month=None, year=None, template_name="accounts/account_history.html"):
    '''
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
    :type month: integer
    :param year: The Year to select, usage requires a specified month.
    :type year: integer
    :param template_name: The template to use.
    :type template_name: string
    :returns: HTTP context with a list of instances or empty string as \
              ``accounts`` and a :class:`~datetime.date` as ``date``
    :rtype: HttpResponse
    :raises Http404: if an invalid ``month`` or ``year`` is specified.
    '''
    # TODO: Display "No Account History For This Date." Instead of redirecting
    # or disable the next/previous buttons if there are none
    if 'next' in request.GET:
        datemod = datetime.timedelta(days=31)
    elif 'previous' in request.GET:
        datemod = datetime.timedelta(days=-1)
    else:
        datemod = datetime.timedelta(0)

    if month is None and year is None:
        # TODO: Refactor "today" into "today" and "this_month_last_year"
        # variables
        today = (datetime.date.today() -
                 datetime.timedelta(datetime.date.today().day - 1))
        accounts = HistoricalAccount.objects.filter(date__month=today.month,
                                                    date__year=today.year - 1)
        max_date = HistoricalAccount.objects.aggregate(Max('date'))['date__max']
        if accounts.exists():
            month = today.month
            year = today.year - 1
        elif max_date is not None:
            month = max_date.month
            year = max_date.year
        else:
            # TODO: No Account History Exists
            return render_to_response(template_name, {'accounts': ''},
                                      context_instance=RequestContext(request))

    try:
        date = datetime.date(day=1, month=int(month), year=int(year)) + datemod
    except ValueError:
        raise Http404
    accounts = HistoricalAccount.objects.filter(date__month=date.month, date__year=date.year)
    date_change = bool('next' in request.GET or 'previous' in request.GET)
    exists = accounts.exists()
    if date_change and exists:
        return HttpResponseRedirect(reverse('accounts.views.show_account_history',
                                            kwargs={'month': date.month,
                                                    'year': date.year}))
    elif exists:
        return render_to_response(template_name, {'accounts': accounts,
                                                  'date': date},
                                  context_instance=RequestContext(request))
    elif date_change:
        return HttpResponseRedirect(reverse('accounts.views.show_account_history',
                                            kwargs={'month': month,
                                                    'year': year}))
    else:
        # TODO: No Account History Exists
        return render_to_response(template_name, {'accounts': '',
                                                  'date': date},
                                  context_instance=RequestContext(request))


def show_event_detail(request, event_id, template_name="accounts/event_detail.html"):
    event = get_object_or_404(Event, id=event_id)
    debit_total, credit_total, net_change = event.transaction_set.get_totals(net_change=True)
    return render_to_response(template_name, locals(),
                              context_instance=RequestContext(request))


# TODO: improve variable names, use underscores between words
def journal_ledger(request, template_name="accounts/journal_ledger.html"):
    form, startdate, stopdate = process_date_range_form(request)
    journal_entries = JournalEntry.objects.filter(date__lte=stopdate,
                                                  date__gte=startdate
                                                  ).order_by('date')
    return render_to_response(template_name, locals(),
                              context_instance=RequestContext(request))


def bank_register(request, account_slug, template_name="accounts/bank_register.html"):
    form, startdate, stopdate = process_date_range_form(request)
    account = get_object_or_404(Account, slug=account_slug, bank=True)
    # TODO: Refactor into Account manager method, get_bank_entries_by_date()
    transactions = Transaction.objects.filter(account=account).filter(
            (Q(bankspendingentry__isnull=False) | Q(bankreceivingentry__isnull=False)) &
            (Q(date__lte=stopdate) & Q(date__gte=startdate)))
    return render_to_response(template_name, locals(),
                              context_instance=RequestContext(request))


# TODO: Refacotr Parameter journal_id to entry_id
def show_journal_entry(request, journal_id, template_name="accounts/entry_detail.html"):
    journal_entry = get_object_or_404(JournalEntry, pk=journal_id)
    # TODO: Refactor into Journal Entry method?
    updated = (journal_entry.created_at.date() !=
               journal_entry.updated_at.date())
    transactions = journal_entry.transaction_set.all()
    debit_total, credit_total = journal_entry.transaction_set.get_totals()
    return render_to_response(template_name, locals(),
                              context_instance=RequestContext(request))


# TODO: Refacotr Parameter journal_id to entry_id
def show_bank_entry(request, journal_id, journal_type):
    entry_types = {'CR': BankReceivingEntry, 'CD': BankSpendingEntry}
    templates = {'CR': 'accounts/entry_bankreceive_detail.html', 'CD': 'accounts/entry_bankspend_detail.html'}
    entry_type = entry_types[journal_type]
    template_name = templates[journal_type]
    journal_entry = get_object_or_404(entry_type, id=journal_id)
    updated = journal_entry.created_at.date() != journal_entry.updated_at.date()
    main_transaction = journal_entry.main_transaction
    transactions = journal_entry.transaction_set.all()
    return render_to_response(template_name, locals(),
                              context_instance=RequestContext(request))


# TODO: Consistent parameter ordering
def add_journal_entry(request, template_name="accounts/entry_add.html", journal_id=None):
    try:
        entry = JournalEntry.objects.get(id=journal_id)
        if not entry.in_fiscal_year():
            raise Http404
        entry.updated_at = timezone.now()
        for transaction in entry.transaction_set.all():
            # TODO: Do this in the form instead
            if transaction.balance_delta < 0:
                transaction.debit = -1 * transaction.balance_delta
            elif transaction.balance_delta > 0:
                transaction.credit = transaction.balance_delta
    except JournalEntry.DoesNotExist:
        entry = JournalEntry()
        entry.date = datetime.date.today

    if request.method == 'POST':
    # TODO: Use "if request.POST.get('subbtn') in ("Submit", ... etc. ):"
        if 'subbtn' in request.POST and (request.POST['subbtn'] == 'Submit' or request.POST['subbtn'] == 'Submit & Add More'):
            entry_form = JournalEntryForm(request.POST, prefix='entry', instance=entry)
            transaction_formset = TransactionFormSet(request.POST, prefix='transaction', instance=entry)
            if entry_form.is_valid():
                entry = entry_form.save(commit=False)
                transaction_formset.entry_form = entry_form
                if transaction_formset.is_valid():
                    entry_form.save()
                    transaction_formset.save(commit=False)
                    for form in transaction_formset.forms:
                        if form.is_valid() and form.has_changed() and form not in transaction_formset.deleted_forms:
                        # TODO: Why work on the instance instead of modelform
                            if transaction_formset.instance is TransactionFormSet:
                                form.instance.journal_entry = entry
                            # TODO: Remove, not needed for JournalEntries
                            elif transaction_formset.instance is BankReceivingTransactionFormSet:
                                form.instance.bankspend_entry = entry
                            elif transaction_formset.instance is BankReceivingTransactionFormSet:
                                form.instance.bankreceive_entry = entry
                            form.instance.balance_delta = form.cleaned_data['balance_delta']
                            form.instance.save()
                    if request.POST['subbtn'] == 'Submit & Add More':
                        return HttpResponseRedirect(reverse('accounts.views.add_journal_entry'))
                    return HttpResponseRedirect(reverse('accounts.views.show_journal_entry',
                                                        kwargs={'journal_id': entry.id}))
        # TODO: request.POST.get() ==
        elif 'delete' in request.POST and request.POST['delete'] == 'Delete':
            if entry.pk:
                entry.delete()
                return HttpResponseRedirect(reverse('accounts.views.journal_ledger'))
            else:
                raise Http404
        else:
            raise Http404
    else:
        entry_form = JournalEntryForm(prefix='entry', instance=entry)
        transaction_formset = TransactionFormSet(prefix='transaction', instance=entry)
        # TODO: Do these in the form instead
        if entry_form.instance.pk:
            entry_form.initial['date'] = entry_form.instance.date.strftime('%m/%d/%Y')
        else:
            entry_form.initial['date'] = american_today()
        for form in transaction_formset.forms:
            if form.instance.pk:
                if form.instance.balance_delta > 0:
                    form.initial['credit'] = form.instance.balance_delta
                elif form.instance.balance_delta < 0:
                    form.initial['debit'] = -1 * form.instance.balance_delta
    return render_to_response(template_name,
                              {'entry_form': entry_form,
                               'journal_type': 'GJ',
                               'transaction_formset': transaction_formset},
                              context_instance=RequestContext(request))


# TODO: journal_id -> entry_id
def add_bank_entry(request, journal_id=None, journal_type='', template_name="accounts/entry_add.html"):
    # TODO: Better variable names, key_to_value for dicts
    entry_types = {'CR': BankReceivingEntry, 'CD': BankSpendingEntry}
    form_types = {'CR': BankReceivingForm, 'CD': BankSpendingForm}
    formset_types = {'CR': BankReceivingTransactionFormSet, 'CD': BankSpendingTransactionFormSet}
    # TODO: Check for invalid journal_type. Use .get() and test for None
    entry_type = entry_types[journal_type]
    EntryTypeForm = form_types[journal_type]
    InlineFormSet = formset_types[journal_type]
    try:
        entry = entry_type.objects.get(id=journal_id)
        if not entry.in_fiscal_year():
            raise Http404
        entry.updated_at = timezone.now()
        for transaction in entry.transaction_set.all():
            # TODO: Do this in the form
            transaction.amount = abs(transaction.balance_delta)
    except entry_type.DoesNotExist:
        entry = entry_type()
        entry.date = datetime.date.today
    if request.method == 'POST':
        # TODO: Refactor using "in ('Submit', 'Submit  & Add More')"
        if 'subbtn' in request.POST and (request.POST['subbtn'] == 'Submit' or request.POST['subbtn'] == 'Submit & Add More'):
            entry_form = EntryTypeForm(request.POST, prefix='entry', instance=entry)
            transaction_formset = InlineFormSet(request.POST, prefix='transaction', instance=entry)
            if entry_form.is_valid():
                transaction_formset.entry_form = entry_form     # Used for clean function
                if transaction_formset.is_valid():
                    entry_form.save()
                    transaction_formset.save(commit=False)
                    for form in transaction_formset.forms:
                        # TODO: Look over this, is there a cleaner way?
                        if form.is_valid() and form.has_changed() and form not in transaction_formset.deleted_forms:
                            # TODO: Is there a better way? at least do this in
                            # the form?
                            if EntryTypeForm is BankSpendingForm:
                                form.instance.bankspend_entry = entry
                                form.instance.balance_delta = -1 * form.cleaned_data['balance_delta']
                            elif EntryTypeForm is BankReceivingForm:
                                form.instance.bankreceive_entry = entry
                                form.instance.balance_delta = form.cleaned_data['balance_delta']
                            form.instance.save()
                    if request.POST['subbtn'] == 'Submit & Add More':
                        return HttpResponseRedirect(reverse('accounts.views.add_bank_entry', kwargs={'journal_type': journal_type})
                                                    + '?bank_account={0}'.format(entry.main_transaction.account.id))
                    return HttpResponseRedirect(reverse('accounts.views.show_bank_entry',
                                                        kwargs={'journal_id': entry.id,
                                                                'journal_type': journal_type}))
        elif 'delete' in request.POST and request.POST['delete'] == 'Delete':
            if entry.pk:
                bank_account = entry.main_transaction.account
                entry.main_transaction.delete()
                entry.delete()
                return HttpResponseRedirect(reverse('accounts.views.bank_register',
                                                kwargs={'account_slug': bank_account.slug}))
            else:
                raise Http404
        else:
            raise Http404
    else:
        entry_form = EntryTypeForm(prefix='entry', instance=entry)
        transaction_formset = InlineFormSet(prefix='transaction', instance=entry)
        if entry.pk:
            # TODO: Look into moving this to the Form's __init__ method
            entry_form.initial['date'] = entry.date.strftime('%m/%d/%Y')
            entry_form.initial['account'] = entry.main_transaction.account
            entry_form.initial['amount'] = abs(entry.main_transaction.balance_delta)
            for form in transaction_formset.forms:
                if not form.empty_permitted:
                    form.initial['amount'] = abs(form.instance.balance_delta)
        else:
            entry_form.initial['date'] = american_today()
            if 'bank_account' in request.GET:
                entry_form.initial['account'] = request.GET['bank_account']
    return render_to_response(template_name,
                              {'entry_form': entry_form,
                               'journal_type': journal_type,
                               'transaction_formset': transaction_formset},
                              context_instance=RequestContext(request))


def add_transfer_entry(request, template_name="accounts/entry_add.html"):
    entry = JournalEntry()
    entry.date = datetime.date.today

    if request.method == 'POST':
        entry_form = JournalEntryForm(request.POST, prefix='entry', instance=entry)
        transfer_formset = TransferFormSet(request.POST, prefix='transfer')
        if entry_form.is_valid():
            entry_form.save(commit=False)
            if transfer_formset.is_valid():
                entry.save()
                for form in transfer_formset.forms:
                    if (form.is_valid() and form.has_changed() and
                            form not in transfer_formset.deleted_forms):
                        # TODO: Move to form's save method
                        debit = Transaction(journal_entry=entry, account=form.cleaned_data['source'],
                                            detail=form.cleaned_data['detail'],
                                            balance_delta=(-1 * form.cleaned_data['amount']))
                        credit = Transaction(journal_entry=entry, account=form.cleaned_data['destination'],
                                            detail=form.cleaned_data['detail'],
                                            balance_delta=(form.cleaned_data['amount']))
                        debit.save()
                        credit.save()
                return HttpResponseRedirect(reverse('accounts.views.show_journal_entry',
                                                    kwargs={'journal_id': entry.id}))
    else:
        entry_form = JournalEntryForm(prefix='entry', instance=entry)
        transfer_formset = TransferFormSet(prefix='transfer')
        # TODO: DO this in the forms init method?
        if entry.pk:
            entry_form.initial['date'] = entry.date.strftime('%m/%d/%Y')
        else:
            entry_form.initial['date'] = american_today()
    return render_to_response(template_name,
                              {'entry_form': entry_form,
                               'transaction_formset': transfer_formset},
                              context_instance=RequestContext(request))


def reconcile_account(request, account_slug, template_name="accounts/account_reconcile.html"):
    account = get_object_or_404(Account, slug=account_slug)
    last_reconciled = account.last_reconciled
    reconciled_transactions = account.transaction_set.filter(reconciled=True)
    if reconciled_transactions.exists():
        reconciled_balance = reconciled_transactions.aggregate(Sum('balance_delta'))['balance_delta__sum']
    else:
        reconciled_balance = 0
    if request.method == 'POST':
        # TODO: Use .get() ==
        if 'submit' in request.POST and request.POST['submit'] == 'Get Transactions':
            account_form = AccountReconcileForm(request.POST, prefix='account', instance=account)
            if account_form.is_valid():
                # TODO: Better variable names
                startdate = last_reconciled
                stopdate = account_form.cleaned_data['statement_date']
                queryset = account.transaction_set.filter(reconciled=False).filter(date__lte=stopdate)
                transaction_formset = ReconcileTransactionFormSet(queryset=queryset)
                return render_to_response(template_name, {'account': account,
                                                          'reconciled_balance': reconciled_balance * (-1 if account.flip_balance() else 1),
                                                          'last_reconciled': last_reconciled,
                                                          'account_form': account_form,
                                                          'transaction_formset': transaction_formset},
                                          context_instance=RequestContext(request))
        # TODO: Use .get() ==
        elif 'submit' in request.POST and request.POST['submit'] == 'Reconcile Transactions':
            account_form = AccountReconcileForm(request.POST, prefix='account', instance=account)
            transaction_formset = ReconcileTransactionFormSet(request.POST)
            if account_form.is_valid():
                transaction_formset.reconciled_balance = reconciled_balance
                transaction_formset.account_form = account_form
                if transaction_formset.is_valid():
                    transaction_formset.save()
                    account.last_reconciled = account_form.cleaned_data['statement_date']
                    account.save()
                    return HttpResponseRedirect(reverse('accounts.views.show_account_detail',
                                                        kwargs={'account_slug': account.slug}))
        else:
            raise Http404
    else:
        account_form = AccountReconcileForm(prefix='account', instance=account, initial={'statement_date': american_today()})
        reconciled_balance = reconciled_balance * (-1 if account.flip_balance() else 1)
    return render_to_response(template_name, locals(),
                              context_instance=RequestContext(request))


def add_fiscal_year(request, template_name="accounts/year_add.html"):
    '''
    Creates a new :class:`FiscalYear` using a :class:`FiscalYearForm` and
    :data:`FiscalYearAccountsFormSet`.

    Starting a new :class:`FiscalYear` involves the following procedure::

        1. Setting a ``period`` and Ending ``month`` and ``year`` for the New
           Fiscal Year.
        2. Selecting Accounts to exclude from purging of unreconciled
           :class:`Transactions`.
        3. Create a :class:`HistoricalAccount` for every :class:`Account` and
           month in the previous :class:`FiscalYear`, using ending balances
           for Asset, Liability and Equity :class:`Accounts<Account>` and
           balance changes for the others.
        4. Delete all :class:`Journal Entries<JournalEntry>`, except those
           with unreconciled :class:`Transactions<Transaction>` with
           :class:`Accounts<Account>` in the exclude lists.
        5. Move the ``balance`` of the ``Current Year Earnings``
           :class:`Account` into the ``Retained Earnings`` :class:`Account`.
        6. Zero the ``balance`` of all Income, Cost of Sales, Expense, Other
           Income and Other Expense :class:`Accounts<Account>`.

    :param template_name: The template to use.
    :type template_name: string
    :returns: HTTP response containing :class:`FiscalYearForm` and \
            :class:`FiscalYearAccountsFormSet` as context. Redirects if \
            successful POST is sent.
    :rtype: HttpResponse or HttpResponseRedirect
    '''
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
            stopdate = previous_year.date
            startdate = FiscalYear.objects.current_start()
            # TODO: Refactor into FiscalYear.objects.current_years_months()
            for month in rrule.rrule(rrule.MONTHLY, dtstart=startdate,
                    until=stopdate):
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
            historical_year_end = previous_year.date.replace(day=
                        calendar.monthrange(previous_year.year,
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
                new_year_sum = account.transaction_set.filter(date__gt=
                        historical_year_end).aggregate(Sum('balance_delta'))
                account.balance = (new_year_sum.get('balance_delta__sum') or
                        0) + hist_acct.amount
                account.save()
            for account in Account.objects.filter(type__in=range(4, 9)):
                # Balances will reflect Transactions in new Year
                new_year_sum = account.transaction_set.filter(
                        date__gt=historical_year_end).aggregate(
                        Sum('balance_delta'))
                account.balance = (new_year_sum.get('balance_delta__sum') or 0)
                account.save()
            # Move balance of Current Year Earnings to Retained Earnings
            # TODO: Refactor out into end_of_year_earnings_transfer()
            current_earnings = Account.objects.get(
                    name='Current Year Earnings')
            retained_earnings = Account.objects.get(name='Retained Earnings')
            hist_current = current_earnings.historicalaccount_set.latest()
            transfer_date = historical_year_end + datetime.timedelta(days=1)
            entry = JournalEntry.objects.create(date=transfer_date,
                    memo='End of Fiscal Year Adjustment')
            Transaction.objects.create(journal_entry=entry,
                                       account=current_earnings,
                                       balance_delta=hist_current.amount * -1)
            Transaction.objects.create(journal_entry=entry,
                                       account=retained_earnings,
                                       balance_delta=hist_current.amount)
            fiscal_year_form.save()
            return HttpResponseRedirect(reverse(
                'accounts.views.show_accounts_chart'))
        elif valid:
            fiscal_year_form.save()
            return HttpResponseRedirect(reverse(
                'accounts.views.show_accounts_chart'))
    else:
        fiscal_year_form = FiscalYearForm()
        accounts_formset = FiscalYearAccountsFormSet()
    return render_to_response(template_name, locals(), RequestContext(request))
