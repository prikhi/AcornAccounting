from decimal import Decimal

from django import forms
from django.forms.formsets import formset_factory
from django.forms.models import inlineformset_factory
from parsley.decorators import parsleyfy

from accounts.models import Account
from core.core import today_in_american_format
from core.forms import RequiredBaseFormSet, RequiredBaseInlineFormSet
from events.models import Event     # Needed for Sphinx
from fiscalyears.fiscalyears import get_start_of_current_fiscal_year

from .models import (Transaction, JournalEntry, BankSpendingEntry,
                     BankReceivingEntry)


class BaseEntryForm(object):
    """An abstraction of General and Bank Entries."""

    def __init__(self, *args, **kwargs):
        """Initialize the date to today and put it in MM/DD/YYYY format."""
        super(BaseEntryForm, self).__init__(*args, **kwargs)
        self._initialize_date()

    def _initialize_date(self):
        """Default to today, formatted as MM/DD/YYYY."""
        if hasattr(self, 'instance') and self.instance.pk:
            formatted_date = self.instance.date.strftime('%m/%d/%Y')
            self.initial['date'] = formatted_date
        else:
            self.initial['date'] = today_in_american_format()

    def clean_date(self):
        """The date must be in the Current :class:`FiscalYear`."""
        input_date = self.cleaned_data.get('date')
        fiscal_year_start = get_start_of_current_fiscal_year()
        if fiscal_year_start is not None and input_date < fiscal_year_start:
            raise forms.ValidationError("The date must be in the current "
                                        "Fiscal Year.")
        return input_date


@parsleyfy
class JournalEntryForm(BaseEntryForm, forms.ModelForm):
    """A form for :class:`JournalEntries<.models.JournalEntry>`."""

    class Meta:
        model = JournalEntry
        widgets = {
            'date': forms.DateInput(attrs={'data-americandate': True,
                                           'class': 'form-control'}),
            'comments': forms.Textarea(attrs={'rows': 2, 'cols': 50,
                                              'class': 'form-control'}),
            'memo': forms.TextInput(attrs={'class': 'form-control'})
        }


@parsleyfy
class TransactionForm(forms.ModelForm):
    """A form for :class:`Transactions<.models.Transaction>`.

    It splits the :attr:`~.models.Transaction.balance_delta` field into a
    ``credit`` and ``debit`` field. A debit results in a negative
    :attr:`~.models.Transaction.balance_delta` and a credit results in a
    positive :attr:`~.models.Transaction.balance_delta`.

    """
    credit = forms.DecimalField(
        required=False, min_value=Decimal("0.01"),
        widget=forms.TextInput(
            attrs={'size': 10, 'maxlength': 10,
                   'class': 'credit form-control enter-mod'})
    )

    debit = forms.DecimalField(
        required=False, min_value=Decimal("0.01"),
        widget=forms.TextInput(
            attrs={'size': 10, 'maxlength': 10,
                   'class': 'debit form-control enter-mod'})
    )

    class Meta:
        model = Transaction
        fields = ('account', 'detail', 'debit', 'credit', 'event',)
        widgets = {
            'account': forms.Select(
                attrs={'class': 'account form-control'}),
            'detail': forms.TextInput(
                attrs={'class': 'form-control enter-mod'}),
            'event': forms.Select(
                attrs={'class': 'form-control enter-mod'}),
        }

    def __init__(self, *args, **kwargs):
        super(TransactionForm, self).__init__(*args, **kwargs)
        _allow_only_active_accounts(self, 'account')
        self._assign_balance_delta_to_debit_or_credit_field()

    def clean(self):
        """
        Make sure only a credit or debit is entered and set it to the
        balance_delta.

        """
        super(TransactionForm, self).clean()
        if any(self.errors) or self.cleaned_data.get('DELETE', False):
            return self.cleaned_data
        cleaned_data = self.cleaned_data
        debit = cleaned_data.get('debit')
        credit = cleaned_data.get('credit')
        if credit and debit:
            raise forms.ValidationError("Please enter only one debit or "
                                        "credit per line.")
        elif credit:
            cleaned_data['balance_delta'] = credit
        elif debit:
            cleaned_data['balance_delta'] = -1 * debit
        else:
            raise forms.ValidationError("Either a credit or a debit is "
                                        "required")
        return cleaned_data

    def _assign_balance_delta_to_debit_or_credit_field(self):
        """
        If the form's :class:`~.models.Transaction` instance has a
        `balance_delta` set either the `credit` or `debit` field to it's
        absolute value, depending on if the balance_delta is positive or
        negative, respectively.

        """
        balance_delta = self.instance.balance_delta
        if balance_delta is not None:
            if balance_delta < 0:
                self.initial['debit'] = abs(balance_delta)
            else:
                self.initial['credit'] = balance_delta


def _allow_only_active_accounts(form_instance, field):
    """Modify the form's field to only display active Accounts."""
    active_accounts = Account.objects.active().order_by('name')
    form_instance.fields[field].queryset = active_accounts


class BaseTransactionFormSet(RequiredBaseInlineFormSet):
    """
    A FormSet that validates that a set of
    :class:`Transactions<.models.Transaction>` is balanced.
    """
    def clean(self):
        """Checks that debits and credits balance out."""
        super(BaseTransactionFormSet, self).clean()
        if any(self.errors):
            return
        balance = Decimal(0)
        for form in self.forms:
            if form.cleaned_data.get('DELETE'):
                continue
            balance += form.cleaned_data.get('balance_delta', 0)
        if balance != 0:
            raise forms.ValidationError("The total amount of Credits must be "
                                        "equal to the total amount of Debits.")
        return


#: A FormSet for :class:`Transactions<.models.Transaction>`, derived from the
#: :class:`BaseTransactionFormSet`.
TransactionFormSet = inlineformset_factory(JournalEntry, Transaction,
                                           extra=20,
                                           form=TransactionForm,
                                           formset=BaseTransactionFormSet,
                                           can_delete=True)


@parsleyfy
class TransferForm(BaseEntryForm, forms.Form):
    """
    A form for Transfer Entries, a specialized :class:`~.models.JournalEntry`.

    Transfer Entries move a discrete :attr:`amount` between two
    :class:`Accounts<accounts.models.Account>`. The :attr:`source` is debited
    while the :attr:`destination` is credited.

    .. attribute:: source

        The :class:`~accounts.models.Account` to remove the amount from.

    .. attribute:: destination

        The :class:`~accounts.models.Account` to move the amount to.

    .. attribute:: amount

        The amount of currency to transfer between
        :class:`Accounts<accounts.models.Account>`.

    .. attribute:: detail

        Any additional details about the charge.

    """
    source = forms.ModelChoiceField(
        queryset=Account.objects.active().order_by('name'),
        widget=forms.Select(attrs={'class': 'source form-control'})
    )
    destination = forms.ModelChoiceField(
        queryset=Account.objects.active().order_by('name'),
        widget=forms.Select(attrs={'class': 'destination form-control'})
    )
    # TODO: This is repeated in BaseBankForm & AccountReconcileForm and ugly
    amount = forms.DecimalField(
        max_digits=19, decimal_places=4, min_value=Decimal("0.01"),
        widget=forms.TextInput(
            attrs={'size': 10, 'maxlength': 10,
                   'class': 'amount form-control enter-mod'})
    )
    detail = forms.CharField(
        max_length=50, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control enter-mod'})
    )

    def clean(self):
        """
        Ensure that the source and destination
        :class:`Accounts<accounts.models.Account>` are not the same.
        """
        super(TransferForm, self).clean()
        if any(self.errors):
            return self.cleaned_data
        cleaned_data = self.cleaned_data
        if cleaned_data.get('source') == cleaned_data.get('destination'):
            raise forms.ValidationError("The Source and Destination Accounts "
                                        "must be different.")
        return cleaned_data


#: A FormSet for Transfer Transactions, derived from the :class:`TransferForm`.
TransferFormSet = formset_factory(TransferForm, extra=20, can_delete=True,
                                  formset=RequiredBaseFormSet)


class BaseBankForm(BaseEntryForm, forms.ModelForm):
    """
    A Base form for common elements between the :class:`BankSpendingForm` and
    the :class:`BankReceivingForm`.

    The ``account`` and ``amount`` fields be used to create the Entries
    ``main_transaction``.

    .. attribute:: account

        The Bank :class:`~accounts.models.Account` the Entry is for.

    .. attribute:: amount

        The total amount this Entry represents.

    """
    account = forms.ModelChoiceField(
        queryset=Account.objects.get_banks(),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    amount = forms.DecimalField(
        min_value=Decimal(".01"),
        widget=forms.TextInput(attrs={'size': 10, 'maxlength': 10,
                                      'id': 'entry_amount',
                                      'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        """
        Pull the initial ``account`` and ``amount`` fields from the
        ``main_transaction``.
        """
        super(BaseBankForm, self).__init__(*args, **kwargs)
        self._initialize_account_and_amount_from_main_transaction()

    def _initialize_account_and_amount_from_main_transaction(self):
        """Use the main_transaction's account and amount."""
        if hasattr(self.instance, 'main_transaction'):
            main_transaction = self.instance.main_transaction
            if main_transaction is not None:
                self.initial['account'] = main_transaction.account
                self.initial['amount'] = abs(main_transaction.balance_delta)

    def clean(self):
        """
        Cleaning the :class:`BaseBankForm` will modify or create the
        :attr:`BankSpendingEntry.main_transaction` or
        :attr:`BankReceivingEntry.main_transaction`.

        The ``main_transaction`` will not be saved until this form's save
        method is called.

        """
        super(BaseBankForm, self).clean()
        if any(self.errors):
            return self.cleaned_data
        cleaned_data = self._update_or_add_main_transaction(self.cleaned_data)
        return cleaned_data

    def _update_or_add_main_transaction(self, cleaned_data):
        """
        Update the form's main_transaction, instantiating one if it does not
        exist.

        """
        account = cleaned_data.get('account')
        amount = cleaned_data.get('amount')
        memo = cleaned_data.get('memo')
        date = cleaned_data.get('date')
        try:
            self.instance.main_transaction.account = account
            self.instance.main_transaction.balance_delta = amount
            self.instance.main_transaction.detail = memo
            self.instance.main_transaction.date = date
            cleaned_data['main_transaction'] = self.instance.main_transaction
        except Transaction.DoesNotExist:
            main_transaction = Transaction(account=account, detail=memo,
                                           balance_delta=amount, date=date)
            cleaned_data['main_transaction'] = main_transaction
            self.instance.main_transaction = main_transaction
        return cleaned_data

    def save(self, *args, **kwargs):
        """
        Saving the :class:`BaseBankFormForm` will save both the
        :class:`BaseBankForm` and the
        :attr:`BankSpendingEntry.main_transaction` or
        :attr:`BankReceivingEntry.main_transaction`.

        """
        self.cleaned_data.get('main_transaction').save()
        self.instance.main_transaction = self.cleaned_data['main_transaction']
        super(BaseBankForm, self).save(*args, **kwargs)


@parsleyfy
class BankSpendingForm(BaseBankForm):
    """A form for the :class:`~.models.BankSpendingEntry` model."""
    class Meta:
        model = BankSpendingEntry
        fields = ('account', 'date', 'ach_payment', 'check_number', 'payee',
                  'memo', 'amount', 'comments')
        # TODO: Move to basebankform?
        widgets = {
            'date': forms.DateInput(attrs={'data-americandate': True,
                                           'class': 'form-control'}),
            'comments': forms.Textarea(attrs={'rows': 2, 'cols': 50,
                                              'class': 'form-control'}),
            'ach_payment': forms.CheckboxInput(attrs={'class':
                                                      'form-control'}),
            'check_number': forms.TextInput(attrs={'class': 'form-control'}),
            'memo': forms.TextInput(attrs={'class': 'form-control'}),
            'payee': forms.TextInput(attrs={'class': 'form-control'}),
        }


@parsleyfy
class BankReceivingForm(BaseBankForm):
    """A form for the :class:`~.models.BankReceivingEntry` model."""
    class Meta:
        model = BankReceivingEntry
        fields = ('account', 'date', 'payor', 'amount', 'memo', 'comments')
        widgets = {
            'date': forms.DateInput(attrs={'data-americandate': True,
                                           'class': 'form-control'}),
            'comments': forms.Textarea(attrs={'rows': 2, 'cols': 50,
                                              'class': 'form-control'}),
            'memo': forms.TextInput(attrs={'class': 'form-control'}),
            'payor': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_amount(self):
        """Negate the ``amount`` field.

        :class:`BankReceivingEntries<.models.BankReceivingEntry>` debit their
        bank :class:`~accounts.models.Account>` so a ``positive`` amount should
        become a ``debit`` and vice versa.

        """
        amount = self.cleaned_data.get('amount')
        return -1 * amount


@parsleyfy
class BankTransactionForm(forms.ModelForm):
    """A form for entry of Bank :class:`Transactions<.models.Transaction>`.

    Bank :class:`Transactions<.models.Transaction>` do not have a ``credit``
    and ``debit`` field, instead they have only an ``amount``. Whether this
    amount is a ``credit`` or ``debit`` depends on if the
    :class:`~.models.Transaction` is related to a
    :class:`.models.BankSpendingEntry` or a :class:`.models.BankSpendingEntry`.

    """
    amount = forms.DecimalField(
        max_digits=19, decimal_places=4, min_value=Decimal("0.01"),
        widget=forms.TextInput(
            attrs={'size': 10, 'maxlength': 10,
                   'class': 'amount form-control enter-mod'})
    )

    class Meta:
        model = Transaction
        fields = ('account', 'detail', 'amount', 'event',)
        widgets = {
            'account': forms.Select(
                attrs={'class': 'account form-control'}),
            'detail': forms.TextInput(
                attrs={'class': 'form-control enter-mod'}),
            'event': forms.Select(
                attrs={'class': 'form-control enter-mod'}),
        }

    def __init__(self, *args, **kwargs):
        super(BankTransactionForm, self).__init__(*args, **kwargs)
        _allow_only_active_accounts(self, 'account')
        self._assign_balance_delta_to_amount_field()

    def clean(self):
        """Set the ``balance_delta`` to the entered ``amount``."""
        super(BankTransactionForm, self).clean()
        if any(self.errors):
            return self.cleaned_data
        cleaned_data = self.cleaned_data
        # TODO: Can we use balance_delta instead of also creating an amount?
        cleaned_data['balance_delta'] = cleaned_data.get('amount')
        return cleaned_data

    def _assign_balance_delta_to_amount_field(self):
        """
        If the instance has a balance_delta, set the amount field to it's
        absolute value.

        """
        balance_delta = self.instance.balance_delta
        if balance_delta is not None:
            self.initial['amount'] = abs(balance_delta)


class BaseBankTransactionFormSet(forms.models.BaseInlineFormSet):
    """An InlineFormSet used to validate it's form's amounts balance with the
    ``self.entry_form``'s amount.

    .. note::

        The ``self.entry_form`` attribute must be set by the view instantiating
        this form.

    """
    def clean(self):
        """Checks that the Transactions' amounts balance the Entry's amount."""
        super(BaseBankTransactionFormSet, self).clean()
        if any(self.errors):
            return self.cleaned_data
        balance = abs(self.entry_form.cleaned_data.get('amount'))
        for form in self.forms:
            if form.cleaned_data.get('DELETE'):
                continue
            balance -= abs(form.cleaned_data.get('amount', 0))
        if balance != 0:
            raise forms.ValidationError("The Entry Amount must equal the "
                                        "total Transaction Amount.")


#: A FormSet of :class:`Transactions<.models.Transaction>` for use with
#: :class:`BankSpendingEntries<.models.BankSpendingEntry>`, derived from the
#: :class:`BaseBankTransactionFormSet`.
BankSpendingTransactionFormSet = inlineformset_factory(
    BankSpendingEntry, Transaction, form=BankTransactionForm,
    formset=BaseBankTransactionFormSet, extra=5, can_delete=True)


#: A FormSet of :class:`Transactions<.models.Transaction>` for use with
#: :class:`BankReceivingEntries<.models.BankReceivingEntry>`, derived from the
#: :class:`BaseBankTransactionFormSet`.
BankReceivingTransactionFormSet = inlineformset_factory(
    BankReceivingEntry, Transaction, form=BankTransactionForm,
    formset=BaseBankTransactionFormSet, extra=5, can_delete=True)
