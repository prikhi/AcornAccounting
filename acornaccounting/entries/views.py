import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render, get_object_or_404
from django.utils import timezone

from core.core import (today_in_american_format,
                       process_month_start_date_range_form)

from .forms import (JournalEntryForm, BankSpendingForm, BankReceivingForm,
                    TransactionFormSet, TransferFormSet,
                    BankReceivingTransactionFormSet,
                    BankSpendingTransactionFormSet)
from .models import (Transaction, JournalEntry, BankSpendingEntry,
                     BankReceivingEntry)


def journal_ledger(request, template_name="entries/journal_ledger.html"):
    """Display a list of :class:`Journal Entries<.models.JournalEntry>`.

    :param template_name: The template to use.
    :type template_name: str
    :returns: HTTP response containing
            :class:`~.models.JournalEntry` instances as context.
    :rtype: :class:`~django.http.HttpResponse`

    """
    form, start_date, stop_date = process_month_start_date_range_form(request)
    journal_entries = JournalEntry.objects.filter(date__lte=stop_date,
                                                  date__gte=start_date
                                                  ).order_by('date')
    return render(request, template_name, locals())


def show_journal_entry(request, entry_id,
                       template_name="entries/entry_detail.html"):
    """Display the details of a :class:`~.models.JournalEntry`.

    :param entry_id: The id of the :class:`~.models.JournalEntry` to display.
    :type entry_id: int
    :param template_name: The template to use.
    :type template_name: str
    :returns: HTTP response containing the
            :class:`~.models.JournalEntry` instance and additional details as
            context.
    :rtype: :class:`~django.http.HttpResponse`

    """
    journal_entry = get_object_or_404(JournalEntry, pk=entry_id)
    # TODO: Refactor into Journal Entry method?
    is_updated = (journal_entry.created_at.date() !=
                  journal_entry.updated_at.date())
    transactions = journal_entry.transaction_set.all()
    debit_total, credit_total = journal_entry.transaction_set.get_totals()
    return render(request, template_name, locals())


def show_bank_entry(request, entry_id, journal_type):
    """
    Display the details of a :class:`~.models.BankSpendingEntry` or
    :class:`~.models.BankReceivingEntry`.

    :param entry_id: The id of the Entry to display.
    :type entry_id: int
    :param journal_type: The bank journal of the Entry(``CD`` or ``CR``).
    :type journal_type: str
    :param template_name: The template to use.
    :type template_name: str
    :returns: HTTP response containing the Entry instance and additional
            details as context.
    :rtype: :class:`~django.http.HttpResponse`

    """
    journal_type_to_entry = {'CR': BankReceivingEntry, 'CD': BankSpendingEntry}
    journal_type_to_template = {'CR': 'entries/entry_bankreceive_detail.html',
                                'CD': 'entries/entry_bankspend_detail.html'}
    entry_type = journal_type_to_entry[journal_type]
    template_name = journal_type_to_template[journal_type]
    journal_entry = get_object_or_404(entry_type, id=entry_id)
    is_updated = (journal_entry.created_at.date() !=
                  journal_entry.updated_at.date())
    main_transaction = journal_entry.main_transaction
    transactions = journal_entry.transaction_set.all()
    return render(request, template_name, locals())


@login_required
def add_journal_entry(request, entry_id=None,
                      template_name="entries/entry_add.html"):
    """Add, Edit or Delete a :class:`~.models.JournalEntry`.

    If there is no :class:`~.models.JournalEntry` with an ``id`` of the
    ``entry_id`` parameter, a new :class:`~.models.JournalEntry` will be
    created.

    If the request contains ``POST`` data, either validate and save the data or
    delete the :class:`~.models.JournalEntry` and all related
    :class:`Transactions<.models.Transaction>`, depending on if a ``submit`` or
    ``delete`` is sent.

    :param entry_id: The id of the Entry to edit. If :obj:`None` then a new
            entry will be created.
    :type entry_id: int
    :param template_name: The template to use.
    :type template_name: str
    :returns: HTTP response containing a :class:`~.forms.JournalEntryForm`,
            a :class:`~.forms.TransactionFormSet` and a ``journal_type`` of
            ``GJ``.
    :rtype: :class:`~django.http.HttpResponse` or
            :class:`~django.http.HttpResponseRedirect`

    """
    try:
        entry = JournalEntry.objects.get(id=entry_id)
        if not entry.in_fiscal_year():
            raise Http404
        entry.updated_at = timezone.now()
        for transaction in entry.transaction_set.all():
            # TODO: Do this in the form instead
            if transaction.balance_delta < 0:
                transaction.debit = -1 * transaction.balance_delta
            elif transaction.balance_delta > 0:
                transaction.credit = transaction.balance_delta
        is_new = False
    except JournalEntry.DoesNotExist:
        entry = JournalEntry()
        entry.date = datetime.date.today
        is_new = True

    if request.method == 'POST':
        if request.POST.get("subbtn") in ("Submit", "Submit & Add More"):
            entry_form = JournalEntryForm(request.POST,
                                          prefix='entry',
                                          instance=entry)
            transaction_formset = TransactionFormSet(request.POST,
                                                     prefix='transaction',
                                                     instance=entry)
            if entry_form.is_valid():
                entry = entry_form.save(commit=False)
                transaction_formset.entry_form = entry_form
                if transaction_formset.is_valid():
                    entry_form.save()
                    transaction_formset.save(commit=False)
                    for form in transaction_formset.forms:
                        if (form.is_valid() and form.has_changed() and
                                form not in transaction_formset.deleted_forms):
                            # TODO: Why work on the instance instead of
                            #       the modelform?
                            form.instance.journal_entry = entry
                            form.instance.balance_delta = form.cleaned_data.  \
                                get('balance_delta')
                            form.instance.save()
                    if is_new:
                        messages.success(request, "A new entry was created.")
                    else:
                        messages.success(request, "The entry was modified.")
                    if request.POST.get('subbtn') == 'Submit & Add More':
                        entrys_american_date = entry.date.strftime('%m/%d/%Y')
                        return HttpResponseRedirect(
                            reverse('entries.views.add_journal_entry') +
                            '?date={0}'.format(entrys_american_date))
                    return HttpResponseRedirect(
                        reverse('entries.views.show_journal_entry',
                                kwargs={'entry_id': entry.id}))
        elif request.POST.get('delete') == 'Delete':
            if entry.pk:
                entry.delete()
                messages.success(request, "The entry and all related "
                                 "transactions were deleted.")
                return HttpResponseRedirect(
                    reverse('entries.views.journal_ledger'))
            else:
                raise Http404
        else:
            raise Http404
    else:
        entry_form = JournalEntryForm(prefix='entry', instance=entry)
        transaction_formset = TransactionFormSet(prefix='transaction',
                                                 instance=entry)
        # TODO: Do these in the form instead
        if entry_form.instance.pk:
            entry_form.initial['date'] = entry_form.instance.date.strftime(
                '%m/%d/%Y')
        elif 'date' in request.GET:
            entry_form.initial['date'] = request.GET.get('date')
        else:
            entry_form.initial['date'] = today_in_american_format()
        for form in transaction_formset.forms:
            if form.instance.pk:
                if form.instance.balance_delta > 0:
                    form.initial['credit'] = form.instance.balance_delta
                elif form.instance.balance_delta < 0:
                    form.initial['debit'] = -1 * form.instance.balance_delta
    request_data = {'entry_form': entry_form,
                    'journal_type': 'GJ',
                    'transaction_formset': transaction_formset}
    return render(request, template_name, request_data)


@login_required
def add_bank_entry(request, entry_id=None, journal_type='',
                   template_name="entries/entry_add.html"):
    """Add, Edit or Delete a :class:`~.models.BankSpendingEntry` or
    :class:`~.models.BankReceivingEntry`.

    A ``journal_type`` of ``CD`` corresponds to
    :class:`BankSpendingEntries<.models.BankSpendingEntry>` while a
    ``journal_type`` of ``CR`` corresponds to
    :class:`BankReceivingEntries<.models.BankReceivingEntry>`

    If there is no :class:`~.models.BankSpendingEntry` or
    :class:`~.models.BankReceivingEntry` with an ``id`` of the ``entry_id``
    parameter, a new :class:`~.models.BankSpendingEntry` or
    :class:`~.models.BankReceivingEntry` will be created.

    If the request contains ``POST`` data, either validate and save the data or
    delete the :class:`~.models.JournalEntry` and all related
    :class:`Transactions<.models.Transaction>`, depending on if a ``submit`` or
    ``delete`` is sent.

    :param entry_id: The id of the Entry to edit. If :obj:`None` then a new
            entry will be created.
    :type entry_id: int
    :param journal_type: The bank journal of the Entry(``CD`` or ``CR``).
    :type journal_type: str
    :param template_name: The template to use.
    :type template_name: str
    :returns: HTTP response containing a :class:`~.forms.JournalEntryForm`,
            a :class:`~.forms.TransactionFormSet` and a ``journal_type`` of
            ``GJ``.
    :rtype: :class:`~django.http.HttpResponse` or
            `~django.http.HttpResponseRedirect`

    """
    journal_type_to_entry = {'CR': BankReceivingEntry, 'CD': BankSpendingEntry}
    journal_type_to_form = {'CR': BankReceivingForm, 'CD': BankSpendingForm}
    journal_type_to_formset = {'CR': BankReceivingTransactionFormSet,
                               'CD': BankSpendingTransactionFormSet}
    entry_type = journal_type_to_entry[journal_type]
    EntryTypeForm = journal_type_to_form[journal_type]
    InlineFormSet = journal_type_to_formset[journal_type]
    try:
        entry = entry_type.objects.get(id=entry_id)
        if not entry.in_fiscal_year():
            raise Http404
        entry.updated_at = timezone.now()
        for transaction in entry.transaction_set.all():
            # TODO: Do this in the form
            transaction.amount = abs(transaction.balance_delta)
        is_new = False
    except entry_type.DoesNotExist:
        entry = entry_type()
        entry.date = datetime.date.today
        is_new = True
    if request.method == 'POST':
        if request.POST.get("subbtn") in ("Submit", "Submit & Add More"):
            entry_form = EntryTypeForm(request.POST,
                                       prefix='entry',
                                       instance=entry)
            transaction_formset = InlineFormSet(request.POST,
                                                prefix='transaction',
                                                instance=entry)
            if entry_form.is_valid():
                # Set attribute for formset's clean method
                transaction_formset.entry_form = entry_form
                if transaction_formset.is_valid():
                    entry_form.save()
                    transaction_formset.save(commit=False)
                    for form in transaction_formset.forms:
                        # TODO: Look over this, is there a cleaner way?
                        if (form.is_valid() and form.has_changed() and form not
                                in transaction_formset.deleted_forms):
                            # TODO: Is there a better way? at least do this in
                            # the form?
                            if EntryTypeForm is BankSpendingForm:
                                form.instance.bankspend_entry = entry
                                form.instance.balance_delta = (
                                    -1 * form.cleaned_data.get('balance_delta')
                                )
                            elif EntryTypeForm is BankReceivingForm:
                                form.instance.bankreceive_entry = entry
                                form.instance.balance_delta = (
                                    form.cleaned_data.get('balance_delta')
                                )
                            form.instance.save()
                    if is_new:
                        messages.success(request, "A new entry was created.")
                    else:
                        messages.success(request, "The entry was modified.")
                    if request.POST.get('subbtn') == 'Submit & Add More':
                        entrys_american_date = entry.date.strftime('%m/%d/%Y')
                        return HttpResponseRedirect(
                            reverse('entries.views.add_bank_entry',
                                    kwargs={'journal_type': journal_type}) +
                            '?bank_account={0}&date={1}'.format(
                                entry.main_transaction.account.id,
                                entrys_american_date)
                        )
                    return HttpResponseRedirect(
                        reverse('entries.views.show_bank_entry',
                                kwargs={'entry_id': entry.id,
                                        'journal_type': journal_type}))
        elif request.POST.get('delete') == 'Delete':
            if entry.pk:
                bank_account = entry.main_transaction.account
                entry.main_transaction.delete()
                entry.delete()
                messages.success(request, "The entry and all related "
                                 "transactions were deleted.")
                return HttpResponseRedirect(
                    reverse('accounts.views.bank_journal',
                            kwargs={'account_slug': bank_account.slug}))
            else:
                raise Http404
        elif request.POST.get('void') == 'Void' and journal_type == 'CD':
            if entry.pk:
                entry.void = True
                entry.save()
                return HttpResponseRedirect(
                    reverse('entries.views.show_bank_entry',
                            kwargs={'entry_id': entry.id,
                                    'journal_type': journal_type}))
            else:
                raise Http404
        else:
            raise Http404
    else:
        entry_form = EntryTypeForm(prefix='entry', instance=entry)
        transaction_formset = InlineFormSet(prefix='transaction',
                                            instance=entry)
        if entry.pk:
            # TODO: Look into moving this to the Form's __init__ method
            entry_form.initial['date'] = entry.date.strftime('%m/%d/%Y')
            entry_form.initial['account'] = entry.main_transaction.account
            entry_form.initial['amount'] = abs(
                entry.main_transaction.balance_delta)
            for form in transaction_formset.forms:
                if not form.empty_permitted:
                    form.initial['amount'] = abs(form.instance.balance_delta)
        elif 'date' in request.GET:
            entry_form.initial['date'] = request.GET.get('date')
        else:
            entry_form.initial['date'] = today_in_american_format()
        if 'bank_account' in request.GET:
            entry_form.initial['account'] = request.GET.get('bank_account')
    return render(request, template_name,
                  {'entry_form': entry_form,
                   'journal_type': journal_type,
                   'transaction_formset': transaction_formset})


@login_required
def add_transfer_entry(request, template_name="entries/entry_add.html"):
    """Add a Transfer Entry, a specialized :class:`~.models.JournalEntry`.

    Transfer Entries are :class:`JournalEntries<.models.JournalEntry>` where a
    discrete amount is being transfered from one account to another.

    Normally, :class:`JournalEntries<.models.JournalEntry>` require that the
    Credit and Debit totals are equal. Transfer Entries require that every
    single Credit charge is balanced with an equal Debit charge.

    Transfer Entries do not have their own class, they use the
    :class:`~.models.JournalEntry` model.

    :param template_name: The template to use.
    :type template_name: str
    :returns: HTTP response containing a :class:`~.forms.JournalEntryForm`,
            a :class:`~.forms.TransferFormSet` and a ``journal_type`` of
            ``Transfer``.
    :rtype: :class:`~django.http.HttpResponse`
    """
    entry = JournalEntry()
    entry.date = datetime.date.today

    if request.method == 'POST':
        entry_form = JournalEntryForm(request.POST,
                                      prefix='entry',
                                      instance=entry)
        transfer_formset = TransferFormSet(request.POST, prefix='transfer')
        if entry_form.is_valid():
            entry_form.save(commit=False)
            if transfer_formset.is_valid():
                entry.save()
                for form in transfer_formset.forms:
                    if (form.is_valid() and form.has_changed() and
                            form not in transfer_formset.deleted_forms):
                        # TODO: Move to form's save method
                        detail = form.cleaned_data.get('detail')
                        amount = form.cleaned_data.get('amount')
                        source = form.cleaned_data.get('source')
                        destination = form.cleaned_data.get('destination')
                        debit = Transaction(journal_entry=entry,
                                            account=source,
                                            detail=detail,
                                            balance_delta=(-1 * amount))
                        credit = Transaction(journal_entry=entry,
                                             account=destination,
                                             detail=detail,
                                             balance_delta=amount)
                        debit.save()
                        credit.save()

                messages.success(request, "A new entry was created.")
                if request.POST.get('subbtn') == 'Submit & Add More':
                    entrys_american_date = entry.date.strftime('%m/%d/%Y')
                    return HttpResponseRedirect(
                        reverse('entries.views.add_transfer_entry') +
                        '?date={0}'.format(entrys_american_date))
                return HttpResponseRedirect(
                    reverse('entries.views.show_journal_entry',
                            kwargs={'entry_id': entry.id}))
    else:
        entry_form = JournalEntryForm(prefix='entry', instance=entry)
        transfer_formset = TransferFormSet(prefix='transfer')
        # TODO: DO this in the forms init method?
        if entry.pk:
            entry_form.initial['date'] = entry.date.strftime('%m/%d/%Y')
        elif 'date' in request.GET:
            entry_form.initial['date'] = request.GET.get('date')
        else:
            entry_form.initial['date'] = today_in_american_format()
    return render(request, template_name,
                  {'entry_form': entry_form,
                   'transaction_formset': transfer_formset,
                   'journal_type': "Transfer"})
