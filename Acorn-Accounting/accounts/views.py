import datetime

from django.db.models import Q, Sum
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render_to_response, get_object_or_404
from django.template.context import RequestContext
from django.utils import timezone

from .accounting import american_today, process_date_range_form
from .forms import JournalEntryForm, TransferFormSet, TransactionFormSet, BankSpendingForm,             \
                   BankReceivingForm, BankReceivingTransactionFormSet, BankSpendingTransactionFormSet,  \
                   AccountReconcileForm, ReconcileTransactionFormSet
from .models import Header, Account, JournalEntry, BankReceivingEntry, BankSpendingEntry, Transaction,  \
                    Event


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
    form, startdate, stopdate = process_date_range_form(request)
    account = get_object_or_404(Account, slug=account_slug)
    query = ((Q(journal_entry__date__lte=stopdate,) & Q(journal_entry__date__gte=startdate)) |
             (Q(bankspend_entry__date__lte=stopdate,) & Q(bankspend_entry__date__gte=startdate)) |
             (Q(bankreceive_entry__date__lte=stopdate,) & Q(bankreceive_entry__date__gte=startdate)) |
             (Q(bankspendingentry__date__lte=stopdate) & Q(bankspendingentry__date__gte=startdate)) |
             (Q(bankreceivingentry__date__lte=stopdate) & Q(bankreceivingentry__date__gte=startdate))
            )
    debit_total, credit_total, net_change = account.transaction_set.get_totals(query=query, net_change=True)
    transactions = list(account.transaction_set.filter(query))
    transactions.sort(key=lambda x: x.get_date())
    if transactions:        # Calculate final balances with math instead of many db queries
        startbalance = transactions[0].get_initial_account_balance()
        endbalance = startbalance
        for transaction in transactions:
            if account.flip_balance():
                endbalance += -1 * transaction.balance_delta
            else:
                endbalance += transaction.balance_delta
            transaction.final_balance = endbalance
    else:
        startbalance = endbalance = 0
    return render_to_response(template_name, locals(),
                              context_instance=RequestContext(request))


def show_event_detail(request, event_id, template_name="accounts/event_detail.html"):
    event = get_object_or_404(Event, id=event_id)
    debit_total, credit_total, net_change = event.transaction_set.get_totals(net_change=True)
    return render_to_response(template_name, locals(),
                              context_instance=RequestContext(request))


def journal_ledger(request, template_name="accounts/journal_ledger.html"):
    form, startdate, stopdate = process_date_range_form(request)
    journal_entries = JournalEntry.objects.all().order_by('date').filter(date__lte=stopdate,
                                                                          date__gte=startdate)
    return render_to_response(template_name, locals(),
                              context_instance=RequestContext(request))


def bank_register(request, account_slug, template_name="accounts/bank_register.html"):
    form, startdate, stopdate = process_date_range_form(request)
    account = get_object_or_404(Account, slug=account_slug, bank=True)
    transactions = list(Transaction.objects.filter(account=account).filter(
                                             (Q(bankspendingentry__isnull=False) | Q(bankreceivingentry__isnull=False)) &
                                             ((Q(bankspendingentry__date__lte=stopdate) & Q(bankspendingentry__date__gte=startdate)) |
                                              (Q(bankreceivingentry__date__lte=stopdate) & Q(bankreceivingentry__date__gte=startdate)))))
    transactions.sort(key=lambda x: x.get_date())
    return render_to_response(template_name, locals(),
                              context_instance=RequestContext(request))


def show_journal_entry(request, journal_id, template_name="accounts/entry_detail.html"):
    journal_entry = get_object_or_404(JournalEntry, pk=journal_id)
    updated = journal_entry.created_at.date() != journal_entry.updated_at.date()
    transactions = journal_entry.transaction_set.all()
    debit_total, credit_total = journal_entry.transaction_set.get_totals()
    return render_to_response(template_name, locals(),
                              context_instance=RequestContext(request))


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


def add_journal_entry(request, template_name="accounts/entry_add.html", journal_id=None):
    try:
        entry = JournalEntry.objects.get(id=journal_id)
        entry.updated_at = timezone.now()
        for transaction in entry.transaction_set.all():
            if transaction.balance_delta < 0:
                transaction.debit = -1 * transaction.balance_delta
            elif transaction.balance_delta > 0:
                transaction.credit = transaction.balance_delta
    except JournalEntry.DoesNotExist:
        entry = JournalEntry()
        entry.date = datetime.date.today

    if request.method == 'POST':
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
                            if transaction_formset.instance is TransactionFormSet:
                                form.instance.journal_entry = entry
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


def add_bank_entry(request, journal_id=None, journal_type='', template_name="accounts/entry_add.html"):
    entry_types = {'CR': BankReceivingEntry, 'CD': BankSpendingEntry}
    form_types = {'CR': BankReceivingForm, 'CD': BankSpendingForm}
    formset_types = {'CR': BankReceivingTransactionFormSet, 'CD': BankSpendingTransactionFormSet}
    entry_type = entry_types[journal_type]
    EntryTypeForm = form_types[journal_type]
    InlineFormSet = formset_types[journal_type]
    try:
        entry = entry_type.objects.get(id=journal_id)
        entry.updated_at = timezone.now()
        for transaction in entry.transaction_set.all():
            transaction.amount = abs(transaction.balance_delta)
    except entry_type.DoesNotExist:
        entry = entry_type()
        entry.date = datetime.date.today
    if request.method == 'POST':
        if 'subbtn' in request.POST and (request.POST['subbtn'] == 'Submit' or request.POST['subbtn'] == 'Submit & Add More'):
            entry_form = EntryTypeForm(request.POST, prefix='entry', instance=entry)
            transaction_formset = InlineFormSet(request.POST, prefix='transaction', instance=entry)
            if entry_form.is_valid():
                transaction_formset.entry_form = entry_form     # Used for clean function
                if transaction_formset.is_valid():
                    try:
                        entry.main_transaction.account = entry_form.cleaned_data['account']
                        entry.main_transaction.balance_delta = entry_form.cleaned_data['amount']
                        entry.main_transaction.detail = entry_form.cleaned_data['memo']
                        entry.main_transaction.save()
                    except Transaction.DoesNotExist:
                        entry.main_transaction = Transaction.objects.create(account=entry_form.cleaned_data['account'],
                                                                            balance_delta=entry_form.cleaned_data['amount'],
                                                                            detail=entry_form.cleaned_data['memo'])
                    entry.save()
                    transaction_formset.save(commit=False)
                    for form in transaction_formset.forms:
                        if form.is_valid() and form.has_changed() and form not in transaction_formset.deleted_forms:
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
                    if form.is_valid() and form.has_changed():
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
        if 'submit' in request.POST and request.POST['submit'] == 'Get Transactions':
            account_form = AccountReconcileForm(request.POST, prefix='account', instance=account)
            if account_form.is_valid():
                startdate = last_reconciled
                stopdate = account_form.cleaned_data['statement_date']
                queryset = account.transaction_set.filter(reconciled=False).filter(
                                                         (Q(journal_entry__date__lte=stopdate,) & Q(journal_entry__date__gte=startdate)) |
                                                         (Q(bankspend_entry__date__lte=stopdate,) & Q(bankspend_entry__date__gte=startdate)) |
                                                         (Q(bankreceive_entry__date__lte=stopdate,) & Q(bankreceive_entry__date__gte=startdate)) |
                                                         (Q(bankspendingentry__date__lte=stopdate) & Q(bankspendingentry__date__gte=startdate)) |
                                                         (Q(bankreceivingentry__date__lte=stopdate) & Q(bankreceivingentry__date__gte=startdate)))
                transaction_formset = ReconcileTransactionFormSet(queryset=queryset)
                return render_to_response(template_name, {'account': account,
                                                          'reconciled_balance': reconciled_balance * (-1 if account.flip_balance() else 1),
                                                          'last_reconciled': last_reconciled,
                                                          'account_form': account_form,
                                                          'transaction_formset': transaction_formset},
                                          context_instance=RequestContext(request))
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
