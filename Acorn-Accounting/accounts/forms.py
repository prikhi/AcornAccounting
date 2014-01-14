import datetime
from dateutil import relativedelta
from decimal import Decimal

from django import forms
from django.forms.formsets import formset_factory
from django.forms.models import (inlineformset_factory, modelformset_factory,
                                 BaseModelFormSet)
from parsley.decorators import parsleyfy

from .models import (Account, JournalEntry, Transaction, BankSpendingEntry,
                     BankReceivingEntry, Event, FiscalYear)


class RequiredFormSetMixin(object):
    """This class ensures at least one form in the formset is filled."""
    def clean(self):
        """Ensure that at least one filled form exists."""
        super(RequiredFormSetMixin, self).clean()
        count = 0
        for form in self.forms:
            if (hasattr(form, 'cleaned_data') and not
                    form.cleaned_data.get('DELETE', True)):
                count += 1
                break

        if count < 1:
            raise forms.ValidationError("At least one Transaction is required "
                                        "to create an Entry.")


class RequiredBaseFormSet(RequiredFormSetMixin, forms.models.BaseFormSet):
    """A BaseFormSet that requires at least one filled form."""


class RequiredBaseInlineFormSet(RequiredFormSetMixin,
                                forms.models.BaseInlineFormSet):
    """A BaseInlineFormSet that requires at least one filled form."""


@parsleyfy
class DateRangeForm(forms.Form):
    startdate = forms.DateField(label="Start Date",
                                widget=forms.DateInput(
                                    attrs={'data-americandate': True,
                                           'size': 8,
                                           'class': 'form-control'})
                                )
    stopdate = forms.DateField(label="Stop Date",
                               widget=forms.DateInput(
                                   attrs={'data-americandate': True,
                                          'size': 8,
                                          'class': 'form-control'})
                               )


class QuickAccountForm(forms.Form):
    account = forms.ModelChoiceField(
        queryset=Account.objects.active().order_by('name'),
        widget=forms.Select(attrs={'onchange': 'this.form.submit();',
                                   'class': 'form-control autocomplete-select',
                                   'placeholder': 'Jump to an Account'}),
        label='', empty_label=''
    )


class QuickBankForm(forms.Form):
    bank = forms.ModelChoiceField(
        queryset=Account.objects.active().order_by('name').filter(bank=True),
        widget=forms.Select(attrs={'onchange': 'this.form.submit();',
                                   'class': 'form-control autocomplete-select',
                                   'placeholder': 'Jump to a Bank Journal'}),
        label='', empty_label=''
    )


class QuickEventForm(forms.Form):
    event = forms.ModelChoiceField(
        queryset=Event.objects.all(), label='', empty_label='',
        widget=forms.Select(attrs={'onchange': 'this.form.submit();',
                                   'class': 'form-control autocomplete-select',
                                   'placeholder': 'Jump to an Event'}),
    )


@parsleyfy
class JournalEntryForm(forms.ModelForm):
    class Meta:
        model = JournalEntry
        widgets = {
            'date': forms.DateInput(attrs={'data-americandate': True,
                                           'class': 'form-control'}),
            'comments': forms.Textarea(attrs={'rows': 2, 'cols': 50,
                                              'class': 'form-control'}),
            'memo': forms.TextInput(attrs={'class': 'form-control'})
        }

    def clean_date(self):
        """The date must be in the Current :class:`FiscalYear`."""
        # TODO: Refactor out into subclass from this and BaseBankForm
        input_date = self.cleaned_data.get('date')
        fiscal_year_start = FiscalYear.objects.current_start()
        if fiscal_year_start is not None and input_date < fiscal_year_start:
            raise forms.ValidationError("The date must be in the current "
                                        "Fiscal Year.")
        return input_date


@parsleyfy
class TransactionForm(forms.ModelForm):
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
        self.fields['account'].queryset = Account.objects.active().order_by(
            'name')

    def clean(self):
        """Make sure only a credit or debit is entered."""
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


class BaseTransactionFormSet(RequiredBaseInlineFormSet):
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


TransactionFormSet = inlineformset_factory(JournalEntry, Transaction,
                                           extra=20,
                                           form=TransactionForm,
                                           formset=BaseTransactionFormSet,
                                           can_delete=True)


@parsleyfy
class TransferForm(forms.Form):
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
        """Check that source and destination are not the same"""
        super(TransferForm, self).clean()
        if any(self.errors):
            return self.cleaned_data
        cleaned_data = self.cleaned_data
        if cleaned_data.get('source') == cleaned_data.get('destination'):
            raise forms.ValidationError("The Source and Destination Accounts "
                                        "must be different.")
        return cleaned_data


TransferFormSet = formset_factory(TransferForm, extra=20, can_delete=True,
                                  formset=RequiredBaseFormSet)


class BaseBankForm(forms.ModelForm):
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

    def clean_date(self):
        """The date must be in the Current :class:`FiscalYear`."""
        date = self.cleaned_data.get('date')
        start = FiscalYear.objects.current_start()
        if start is not None and date < start:
            raise forms.ValidationError("The date must be in the current "
                                        "Fiscal Year.")
        return date

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
        cleaned_data = self.cleaned_data
        # TODO: Factor out following into a update_main_transaction() method
        account = cleaned_data.get('account')
        amount = cleaned_data.get('amount')
        memo = cleaned_data.get('memo')
        date = cleaned_data.get('date')
        try:
            # TODO: Use "if hasattr(...):"?
            self.instance.main_transaction.account = account
            self.instance.main_transaction.balance_delta = amount
            self.instance.main_transaction.detail = memo
            self.instance.main_transaction.date = date
            cleaned_data['main_transaction'] = self.instance.main_transaction
        except Transaction.DoesNotExist:
            main_transaction = Transaction(account=account,
                                           balance_delta=amount, detail=memo,
                                           date=date)
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
    class Meta:
        model = BankSpendingEntry
        fields = ('account', 'date', 'ach_payment', 'check_number', 'payee',
                  'amount', 'memo', 'comments')
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
        """Should be negative(debit) for receiving money."""
        amount = self.cleaned_data.get('amount')
        return -1 * amount


@parsleyfy
class BankTransactionForm(forms.ModelForm):
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
        self.fields['account'].queryset = Account.objects.active().order_by(
            'name')

    def clean(self):
        super(BankTransactionForm, self).clean()
        if any(self.errors):
            return self.cleaned_data
        cleaned_data = self.cleaned_data
        # TODO: Can we use balance_delta instead of also creating an amount?
        cleaned_data['balance_delta'] = cleaned_data.get('amount')
        return cleaned_data


class BaseBankTransactionFormSet(forms.models.BaseInlineFormSet):
    def clean(self):
        """Checks that Transaction amounts balance Entry amount"""
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

BankSpendingTransactionFormSet = inlineformset_factory(
    BankSpendingEntry, Transaction, form=BankTransactionForm,
    formset=BaseBankTransactionFormSet, extra=5, can_delete=True)

BankReceivingTransactionFormSet = inlineformset_factory(
    BankReceivingEntry, Transaction, form=BankTransactionForm,
    formset=BaseBankTransactionFormSet, extra=5, can_delete=True)


@parsleyfy
class AccountReconcileForm(forms.ModelForm):
    statement_date = forms.DateField(widget=forms.DateInput(
        attrs={'data-americandate': True,
               'class': 'form-control'}))
    statement_balance = forms.DecimalField(widget=forms.TextInput(
        attrs={'class': 'form-control'}))

    class Meta:
        model = Account
        fields = ('statement_date', 'statement_balance')

    def clean_statement_balance(self):
        balance = self.cleaned_data.get('statement_balance')
        if self.instance.flip_balance():
            balance *= -1
        return balance

    def clean_statement_date(self):
        statement_date = self.cleaned_data.get('statement_date')
        if (self.instance.last_reconciled is not None and
                statement_date < self.instance.last_reconciled):
            raise forms.ValidationError("The Statement Date must be later "
                                        "than the Last Reconciled Date.")
        return statement_date


class BaseReconcileTransactionFormSet(BaseModelFormSet):
    class Meta:
        model = Transaction
        widgets = {
            'reconciled': forms.CheckboxInput(attrs={'class': 'form-control'})
        }

    def clean(self):
        """Checks that Reconciled amounts balance with the Statement amount."""
        super(BaseReconcileTransactionFormSet, self).clean()
        if any(self.errors):
            return self.cleaned_data
        balance = (self.account_form.cleaned_data.get('statement_balance') -
                   self.reconciled_balance)
        for form in self.forms:
            if form.cleaned_data.get('reconciled'):
                balance -= form.instance.balance_delta
        if balance != 0:
            raise forms.ValidationError("The selected Transactions are out of "
                                        "balance with the Statement Amount.")

ReconcileTransactionFormSet = modelformset_factory(
    Transaction, extra=0, can_delete=False, fields=('reconciled',),
    formset=BaseReconcileTransactionFormSet)


@parsleyfy
class FiscalYearForm(forms.ModelForm):
    """
    This form is used to create new :class:`Fiscal Years<FiscalYear>`.

    The form validates the period length against the new Fiscal Year's End
    Month and Year. To pass validation, the new Year must be greater than any
    previous years and the end Month must create a period less than or equal to
    the selected Period.

    .. seealso::

        View :func:`add_fiscal_year`
            The :func:`add_fiscal_year` view processes all actions required for
            starting a New Fiscal Year.

        Form :class:`BaseFiscalYearAccountsFormSet`
            This form processes the accounts to exclude in the New Fiscal Year
            Transaction purging.

    """
    class Meta:
        model = FiscalYear
        widgets = {
            'year': forms.TextInput(attrs={'maxlength': 4, 'size': 4,
                                           'class': 'form-control'}),
            'end_month': forms.Select(attrs={'class': 'form-control'}),
            'period': forms.Select(attrs={'class': 'form-control'}),
        }

    def clean_year(self):
        """
        Validates that the entered ``Year`` value.

        The value is required to be greater than or equal to any previously
        entered ``Year``.

        """
        new_fiscal_year = self.cleaned_data.get('year')
        current_year = FiscalYear.objects.current_start()
        if current_year and new_fiscal_year < current_year.year:
            raise forms.ValidationError("The Year cannot be before the "
                                        "current Year.")
        return new_fiscal_year

    def clean(self):
        """
        Validates that Accounts Exist and that the Year is in the allowed range

        Validates that no previous year's ending month is within the entered
        ``Period`` with respect to the entered ``end_month``.

        If the form causes a period change from 13 to 12 months, the method
        will ensure that there are no :class:`Transactions<Transaction>` in the
        13th month of the last :class:`FiscalYear`.

        If there are previous :class:`FiscalYears<FiscalYear>` the method will
        make sure there are both a ``Current Year Earnings`` and
        ``Retained Earnings`` Equity :class:`Accounts<Account>` with an
        :attr:`Account.type` of ``3``.

        """
        super(FiscalYearForm, self).clean()
        if any(self.errors):
            return self.cleaned_data
        cleaned_data = self.cleaned_data
        if FiscalYear.objects.count() > 0:
            retained = Account.objects.filter(name="Retained Earnings",
                                              type=3).exists()
            current = Account.objects.filter(name="Current Year Earnings",
                                             type=3).exists()
            if not (retained and current):
                raise forms.ValidationError(
                    "'Current Year Earnings' and 'Retained Earnings' Equity "
                    "Accounts are required to start a new Fiscal Year.")
            latest = FiscalYear.objects.latest()
            new_date = datetime.date(cleaned_data.get('year'),
                                     cleaned_data.get('end_month'), 1)
            max_date = latest.date + relativedelta.relativedelta(
                months=cleaned_data.get('period'))
            if new_date <= latest.date:
                raise forms.ValidationError("The new ending Date must be "
                                            "after the current ending Date.")
            elif new_date > max_date:
                raise forms.ValidationError("The new ending Date cannot be "
                                            "greater than the current ending "
                                            "Date plus the new period.")
            if latest.period == 13 and cleaned_data.get('period') == 12:
                trans_in_end_month = Transaction.objects.filter(
                    date__year=latest.year,
                    date__month=latest.end_month).exists()
                if trans_in_end_month:
                    raise forms.ValidationError(
                        "When switching from a 13 month to 12 month period, "
                        "no Transactions can be in the last Year's 13th "
                        "month.")
        return cleaned_data


class FiscalYearAccountsForm(forms.ModelForm):
    """
    This form is used to select whether to exclude an account from the
    :class:`Transaction` purging caused by the :func:`new_fiscal_year` view.
    Selected :class:`Accounts<Account>` will retain their unreconciled
    :class:`Transactions<Transaction>`.

    This form is used by the :func:`~django.forms.models.modelformset_factory`
    to create the :data:`FiscalYearAccountsFormSet`.

    .. seealso::

        View :func:`add_fiscal_year`
            This view processes all actions required for starting a New Fiscal
            Year.

    """
    exclude = forms.BooleanField(required=False)

    class Meta:
        model = Account

    def __init__(self, *args, **kwargs):
        """
        Mark an :class:`Account` for exclusion if it has been reconciled.
        """
        super(FiscalYearAccountsForm, self).__init__(*args, **kwargs)
        self.fields['exclude'].initial = bool(self.instance.last_reconciled)

FiscalYearAccountsFormSet = modelformset_factory(Account, extra=0,
                                                 can_delete=False,
                                                 fields=('exclude',),
                                                 form=FiscalYearAccountsForm)
