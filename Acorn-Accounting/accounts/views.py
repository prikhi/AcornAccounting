import datetime

from django.db.models import Q
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404
from django.template.context import RequestContext

from .accounting import process_date_range_form
from .forms import JournalEntryForm, TransferFormSet, TransactionFormSet
from .models import Header, Account, JournalEntry, BankReceivingEntry, BankSpendingEntry, Transaction
from accounts.forms import BankSpendingForm, BankReceivingForm,\
    BankReceivingTransactionFormSet, BankSpendingTransactionFormSet


def quick_account_search(request):
    '''Processes search for quick_account tag'''
    account = get_object_or_404(Account, pk=request.GET['account'])
    return HttpResponseRedirect(reverse('show_account_detail', args=[account.slug]))


def show_accounts_chart(request, header_slug=None, template_name="accounts/account_charts.html"):
    '''Retrieves self and descendant Headers or all Headers'''
    if header_slug:
        header = Header.objects.get(slug=header_slug)
        nodes = header.get_descendants(include_self=True)
    else:
        nodes = Header.objects.all()

    return render_to_response(template_name,
                              {'nodes': nodes},
                              context_instance=RequestContext(request))


def show_account_detail(request, account_slug,
                        template_name="accounts/account_detail.html"):
    form, startdate, stopdate = process_date_range_form(request)
    account = get_object_or_404(Account, slug=account_slug)
    query = ((Q(journal_entry__date__lte=stopdate,) & Q(journal_entry__date__gte=startdate)) |
             (Q(bankspend_entry__date__lte=stopdate,) & Q(bankspend_entry__date__gte=startdate)) |
             (Q(bankspendingentry__date__lte=stopdate,) & Q(bankspendingentry__date__gte=startdate)) |
             (Q(bankreceive_entry__date__lte=stopdate,) & Q(bankreceive_entry__date__gte=startdate))
            )
    transactions = list(account.transaction_set.filter(query))
    transactions.sort(key=lambda x: x.get_date())
    if transactions:        # Calculate final balances with simple math instead of many db queries
        startbalance = transactions[0].get_initial_account_balance()
        endbalance = startbalance
        for transaction in transactions:
            if account.flip_balance():
                endbalance += -1 * transaction.balance_delta
            else:
                endbalance += transaction.balance_delta
            transaction.final_balance = endbalance
    return render_to_response(template_name, locals(),
                              context_instance=RequestContext(request))


def journal_ledger(request, template_name="accounts/journal_ledger.html"):
    form, startdate, stopdate = process_date_range_form(request)
    journal_entries = JournalEntry.objects.all().order_by('date').filter(date__lte=stopdate,
                                                                          date__gte=startdate)
    return render_to_response(template_name, locals(),
                              context_instance=RequestContext(request))


def show_journal_entry(request, journal_id, journal_type="GJ",
                       template_name="accounts/entry_detail.html"):
    entry_types = {'GJ': JournalEntry, 'CR': BankReceivingEntry, 'CD': BankSpendingEntry}
    entry_type = entry_types[journal_type]
    journal_entry = get_object_or_404(entry_type, pk=journal_id)
    transactions = journal_entry.transaction_set.all()
    return render_to_response(template_name, locals(),
                              context_instance=RequestContext(request))


def add_journal_entry(request, template_name="accounts/entry_add.html", journal_id=None, journal_type='GJ'):
    entry_types = {'GJ': JournalEntry, 'CR': BankReceivingEntry, 'CD': BankSpendingEntry}
    form_types = {'GJ': JournalEntryForm, 'CR': BankReceivingForm, 'CD': BankSpendingForm}
    formset_types = {'GJ': TransactionFormSet, 'CR': BankReceivingTransactionFormSet, 'CD': BankSpendingTransactionFormSet}
    entry_type = entry_types[journal_type]
    EntryTypeForm = form_types[journal_type]
    InlineFormSet = formset_types[journal_type]
    try:
        entry = entry_type.objects.get(id=journal_id)
        entry.updated_at = datetime.datetime.now()
        for transaction in entry.transaction_set.all():
            if transaction.balance_delta < 0:
                transaction.debit = -1 * transaction.balance_delta
            elif transaction.balance_delta > 0:
                transaction.credit = transaction.balance_delta
    except entry_type.DoesNotExist:
        entry = entry_type()
        entry.date = datetime.date.today

    if request.method == 'POST':
        entry_form = EntryTypeForm(request.POST, prefix='entry', instance=entry)
        transaction_formset = InlineFormSet(request.POST, prefix='transaction', instance=entry)
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
                return HttpResponseRedirect(reverse('accounts.views.show_journal_entry',
                                                    kwargs={'journal_id': entry.id,
                                                            'journal_type': journal_type}))
    else:
        entry_form = EntryTypeForm(prefix='entry', instance=entry)
        transaction_formset = InlineFormSet(prefix='transaction', instance=entry)
        for form in transaction_formset.forms:
            if form.instance.pk:
                if form.instance.balance_delta > 0:
                    form.initial['credit'] = form.instance.balance_delta
                elif form.instance.balance_delta < 0:
                    form.initial['debit'] = -1 * form.instance.balance_delta
    return render_to_response(template_name,
                              {'entry_form': entry_form,
                               'journal_type': journal_type,
                               'transaction_formset': transaction_formset},
                              context_instance=RequestContext(request))


def add_bank_entry(request, template_name="accounts/entry_add.html", journal_id=None, journal_type=''):
    entry_types = {'CR': BankReceivingEntry, 'CD': BankSpendingEntry}
    form_types = {'CR': BankReceivingForm, 'CD': BankSpendingForm}
    formset_types = {'CR': BankReceivingTransactionFormSet, 'CD': BankSpendingTransactionFormSet}
    entry_type = entry_types[journal_type]
    EntryTypeForm = form_types[journal_type]
    InlineFormSet = formset_types[journal_type]
    try:
        entry = entry_type.objects.get(id=journal_id)
        entry.updated_at = datetime.datetime.now()
        for transaction in entry.transaction_set.all():
            transaction.amount = abs(transaction.balance_delta)
    except entry_type.DoesNotExist:
        entry = entry_type()
        entry.date = datetime.date.today
    if request.method == 'POST':
        entry_form = EntryTypeForm(request.POST, prefix='entry', instance=entry)
        transaction_formset = InlineFormSet(request.POST, prefix='transaction', instance=entry)
        if entry_form.is_valid():
            entry = entry_form.save(commit=False)
            transaction_formset.entry_form = entry_form
            if transaction_formset.is_valid():
                try:
                    entry.main_transaction.account = entry_form.cleaned_data['account']
                    entry.main_transaction.balance_delta = entry_form.cleaned_data['amount']
                    entry.main_transaction.detail = entry_form.cleaned_data['memo']
                    entry.main_transaction.save()
                except Transaction.DoesNotExist:
                    main_transaction = Transaction(account=entry_form.cleaned_data['account'],
                                                         balance_delta=entry_form.cleaned_data['amount'], detail=entry_form.cleaned_data['memo'])
                    main_transaction.save()
                    entry.main_transaction_id = main_transaction.id
                entry.save()
                transaction_formset.save(commit=False)
                for form in transaction_formset.forms:
                    if form.is_valid() and form.has_changed() and form not in transaction_formset.deleted_forms:
                        if transaction_formset.instance is BankReceivingTransactionFormSet:
                            form.instance.bankspend_entry = entry
                        elif transaction_formset.instance is BankReceivingTransactionFormSet:
                            form.instance.bankreceive_entry = entry
                        form.instance.balance_delta = form.cleaned_data['balance_delta']
                        form.instance.save()
                return HttpResponseRedirect(reverse('accounts.views.show_journal_entry',
                                                    kwargs={'journal_id': entry.id,
                                                            'journal_type': journal_type}))
    else:
        entry_form = EntryTypeForm(prefix='entry', instance=entry)
        transaction_formset = InlineFormSet(prefix='transaction', instance=entry)
        for form in transaction_formset.forms:
            if form.instance.pk:
                if form.instance.balance_delta > 0:
                    form.initial['credit'] = form.instance.balance_delta
                elif form.instance.balance_delta < 0:
                    form.initial['debit'] = -1 * form.instance.balance_delta
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
                                                    kwargs={'journal_id': entry.id,
                                                            'journal_type': 'GJ'}))
    else:
        entry_form = JournalEntryForm(prefix='entry', instance=entry)
        transfer_formset = TransferFormSet(prefix='transfer')
    return render_to_response(template_name,
                              {'entry_form': entry_form,
                               'transaction_formset': transfer_formset},
                              context_instance=RequestContext(request))
