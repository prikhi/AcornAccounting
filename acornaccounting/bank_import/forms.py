"""Forms & Formsets Used in the ``import_bank`` Views."""
from django import forms
from django.forms.formsets import formset_factory

from accounts.models import Account
from entries.forms import BankSpendingForm, TransferForm, BankReceivingForm
from entries.models import (JournalEntry, BankSpendingEntry,
                            BankReceivingEntry, Transaction)

from .models import BankAccount


class BankAccountForm(forms.Form):
    """A Form to Select a BankAccount and Upload an Import File."""

    import_file = forms.FileField()
    bank_account = forms.ModelChoiceField(
        queryset=BankAccount.objects,
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class ImportFormMixin(object):
    """A mixin to help customize Import specific Forms."""

    def _set_account_queryset_from_initial(self, field_name):
        """Set a blank Queryset or one containing the initial field value."""
        if self.is_bound:
            return
        if hasattr(self, 'initial') and field_name in self.initial:
            self.fields[field_name].queryset = Account.objects.filter(
                id=self.initial[field_name])
        else:
            self.fields[field_name].queryset = Account.objects.none()

    def _initialize_date(self):
        """Format the initial date as MM/DD/YYYY."""
        if hasattr(self, 'initial') and 'date' in self.initial:
            self.initial['date'] = self.initial['date'].strftime('%m/%d/%Y')


class TransferImportForm(ImportFormMixin, TransferForm):
    """A form for importing unmatched Transfers."""

    date = forms.DateField(
        widget=forms.DateInput(
            attrs={'data-americandate': True, 'class': 'form-control',
                   'size': 8}))

    memo = forms.CharField(
        max_length=50, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control enter-mod'}))

    def __init__(self, *args, **kwargs):
        """Set the initial Source/Destination Querysets & fix field order."""
        super(TransferImportForm, self).__init__(*args, **kwargs)
        self._set_account_queryset_from_initial('source')
        self._set_account_queryset_from_initial('destination')
        self.fields.keyOrder = (
            'date', 'source', 'destination', 'memo', 'amount')

    def save(self):
        """Save the Transfer by Creating a General Journal Entry."""
        cleaned_data = self.cleaned_data
        entry = JournalEntry.objects.create(
            date=cleaned_data.get('date'), memo='Bank Transfer')
        Transaction.objects.create(
            journal_entry=entry, account=cleaned_data.get('source'),
            balance_delta=cleaned_data.get('amount'), date=entry.date,
        )
        Transaction.objects.create(
            journal_entry=entry, account=cleaned_data.get('destination'),
            balance_delta=-1 * cleaned_data.get('amount'), date=entry.date,
        )


TransferImportFormSet = formset_factory(
    TransferImportForm, extra=0, can_delete=False)


class SpendingImportForm(ImportFormMixin, BankSpendingForm):
    """A form for importing unmatched BankSpendingEntries."""

    expense_account = forms.ModelChoiceField(
        queryset=Account.objects.active().order_by('name'),
        widget=forms.Select(attrs={
            'class': 'account-autocomplete form-control enter-mod account'}))

    class Meta(object):
        """Remove the ``comments`` field from the base BankSpendingForm."""

        model = BankSpendingEntry

        fields = ("date", "expense_account", "ach_payment", "check_number",
                  "payee", "memo", "amount", "account")

        widgets = {
            'date': forms.DateInput(
                attrs={'data-americandate': True, 'size': 8,
                       'class': 'form-control enter-mod',
                       }),
            'ach_payment': forms.CheckboxInput(
                attrs={'class': 'form-control enter-mod'}),
            'check_number': forms.TextInput(
                attrs={'class': 'form-control enter-mod', 'size': 8}),
            'memo': forms.TextInput(
                attrs={'class': 'form-control enter-mod'}),
            'payee': forms.TextInput(
                attrs={'class': 'form-control enter-mod'}),
        }

    def __init__(self, *args, **kwargs):
        """Hide the ``account`` input, fix field labels."""
        super(SpendingImportForm, self).__init__(*args, **kwargs)
        self.fields['account'].widget = forms.HiddenInput()
        self.fields['ach_payment'].label = "ACH"
        self.fields['amount'].widget = forms.TextInput(
            attrs={'size': 10, 'maxlength': 10,
                   'class': 'form-control enter-mod'})
        self._set_account_queryset_from_initial('expense_account')

    def save(self, *args, **kwargs):
        """Create the BankSpendingEntry and it's Transactions."""
        cleaned_data = self.cleaned_data
        main_transaction = Transaction.objects.create(
            date=cleaned_data.get('date'), account=cleaned_data.get('account'),
            balance_delta=cleaned_data.get('amount'),)
        if cleaned_data.get('ach_payment'):
            entry_kwargs = {'ach_payment': True}
        else:
            entry_kwargs = {'check_number': cleaned_data.get('check_number')}
        entry = BankSpendingEntry.objects.create(
            main_transaction=main_transaction, date=cleaned_data.get('date'),
            memo=cleaned_data.get('memo'), payee=cleaned_data.get('payee'),
            **entry_kwargs)
        Transaction.objects.create(
            bankspend_entry=entry, account=cleaned_data.get('expense_account'),
            balance_delta=-1 * cleaned_data.get('amount'))


SpendingImportFormSet = formset_factory(
    SpendingImportForm, extra=0, can_delete=False)


class ReceivingImportForm(ImportFormMixin, BankReceivingForm):
    """A form for importing unmatched BankReceivingEntries."""

    receiving_account = forms.ModelChoiceField(
        queryset=Account.objects.active().order_by('name'),
        widget=forms.Select(attrs={
            'class': 'account-autocomplete form-control enter-mod account'}))

    class Meta(object):
        """Customize the field order & widgets."""

        model = BankReceivingEntry
        fields = ('date', 'receiving_account', 'payor', 'memo', 'amount')
        widgets = {
            'date': forms.DateInput(
                attrs={'data-americandate': True,
                       'class': 'form-control enter-mod', 'size': 8}),
            'memo': forms.TextInput(
                attrs={'class': 'form-control enter-mod'}),
            'payor': forms.TextInput(
                attrs={'class': 'form-control enter-mod'}),
        }

    def __init__(self, *args, **kwargs):
        """Hide the ``account`` input."""
        super(ReceivingImportForm, self).__init__(*args, **kwargs)
        self.fields['account'].widget = forms.HiddenInput()
        self.fields['amount'].widget = forms.TextInput(
            attrs={'size': 10, 'maxlength': 10,
                   'class': 'form-control enter-mod'})
        self._set_account_queryset_from_initial('receiving_account')

    def save(self, *args, **kwargs):
        """Create the BankReceivingEntry and it's Transactions."""
        cleaned_data = self.cleaned_data
        main_transaction = Transaction.objects.create(
            date=cleaned_data.get('date'), account=cleaned_data.get('account'),
            balance_delta=cleaned_data.get('amount'))
        entry = BankReceivingEntry.objects.create(
            main_transaction=main_transaction, date=cleaned_data.get('date'),
            memo=cleaned_data.get('memo'), payor=cleaned_data.get('payor'))
        Transaction.objects.create(
            bankreceive_entry=entry,
            account=cleaned_data.get('receiving_account'),
            balance_delta=-1 * cleaned_data.get('amount'))

ReceivingImportFormSet = formset_factory(
    ReceivingImportForm, extra=0, can_delete=False)
