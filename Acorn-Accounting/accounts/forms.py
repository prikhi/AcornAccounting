import datetime
from dateutil import relativedelta
from decimal import Decimal

from django import forms
from django.db.models import Max
from django.forms.formsets import formset_factory
from django.forms.models import inlineformset_factory, modelformset_factory, BaseModelFormSet
from parsley.decorators import parsleyfy

from .models import Account, JournalEntry, Transaction, BankSpendingEntry, \
                    BankReceivingEntry, Event, FiscalYear


class RequiredInlineFormSet(forms.models.BaseFormSet):
    def __init__(self, *args, **kwargs):
        super(RequiredInlineFormSet, self).__init__(*args, **kwargs)
        self.forms[0].empty_permitted = False


@parsleyfy
class DateRangeForm(forms.Form):
    startdate = forms.DateField(label="Start Date")
    stopdate = forms.DateField(label="Stop Date")


class QuickAccountForm(forms.Form):
    account = forms.ModelChoiceField(queryset=Account.objects.all(),
                                     widget=forms.Select(attrs={'onchange': 'this.form.submit();'}),
                                     label='', empty_label='Jump to an Account')


class QuickBankForm(forms.Form):
    bank = forms.ModelChoiceField(queryset=Account.objects.filter(bank=True),
                                     widget=forms.Select(attrs={'onchange': 'this.form.submit();'}),
                                     label='', empty_label='Jump to a Register')


class QuickEventForm(forms.Form):
    event = forms.ModelChoiceField(queryset=Event.objects.all(),
                                     widget=forms.Select(attrs={'onchange': 'this.form.submit();'}),
                                     label='', empty_label='Jump to an Event')


@parsleyfy
class JournalEntryForm(forms.ModelForm):
    class Meta:
        model = JournalEntry
        widgets = {'date': forms.DateInput(attrs={'data-americandate': True})}

    def clean_date(self):
        '''The date must be in the Current :class:`FiscalYear`.'''
        date = self.cleaned_data.get('date')
        start = FiscalYear.objects.current_start()
        if start is not None and date < start:
            raise forms.ValidationError("The date must be in the current "
                    "Fiscal Year.")
        return date


@parsleyfy
class TransactionForm(forms.ModelForm):
    credit = forms.DecimalField(required=False, min_value=Decimal("0.01"),
                                widget=forms.TextInput(attrs={'size': 10, 'maxlength': 10,
                                                              'class': 'credit'}))
    debit = forms.DecimalField(required=False, min_value=Decimal("0.01"),
                                widget=forms.TextInput(attrs={'size': 10, 'maxlength': 10,
                                                              'class': 'debit'}))

    class Meta:
        model = Transaction
        fields = ('account', 'detail', 'debit', 'credit', 'event',)
        widgets = {'account': forms.Select(attrs={'class': 'account'})}

    def clean(self):
        '''Make sure only a credit or debit is entered'''
        super(TransactionForm, self).clean()
        if any(self.errors):
            return self.cleaned_data
        debit = self.cleaned_data['debit']
        credit = self.cleaned_data['credit']
        if credit and debit:
            raise forms.ValidationError("Only debit OR credit!")
        elif credit:
            self.cleaned_data['balance_delta'] = credit
        elif debit:
            self.cleaned_data['balance_delta'] = -1 * debit
        else:
            raise forms.ValidationError("Enter a credit or debit")
        return self.cleaned_data


class BaseTransactionFormSet(forms.models.BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super(BaseTransactionFormSet, self).__init__(*args, **kwargs)
        self.forms[0].empty_permitted = False

    def clean(self):
        '''Checks that debits and credits balance out'''
        super(BaseTransactionFormSet, self).clean()
        if any(self.errors):
            return
        cleaned_data = self.cleaned_data
        balance = Decimal(0)
        for form in self.forms:
            if form.cleaned_data.get('DELETE'):
                continue
            balance += form.cleaned_data.get('balance_delta', 0)
        if balance != 0:
            raise forms.ValidationError("Transactions are out of balance.")
        return cleaned_data


TransactionFormSet = inlineformset_factory(JournalEntry, Transaction,
                                           extra=20,
                                           form=TransactionForm,
                                           formset=BaseTransactionFormSet,
                                           can_delete=True)


@parsleyfy
class TransferForm(forms.Form):
    source = forms.ModelChoiceField(queryset=Account.objects.all(),
            widget=forms.Select(attrs={'class': 'source'}))
    destination = forms.ModelChoiceField(queryset=Account.objects.all(),
            widget=forms.Select(attrs={'class': 'destination'}))
    amount = forms.DecimalField(max_digits=19,
            decimal_places=4,
            min_value=Decimal("0.01"),
            widget=forms.TextInput(attrs={'size': 10,
                                          'maxlength': 10,
                                          'class': 'amount'}))
    detail = forms.CharField(max_length=50, required=False)

    def clean(self):
        '''Check that source and destination are not the same'''
        super(TransferForm, self).clean()
        if any(self.errors):
            return
        cleaned_data = self.cleaned_data
        if cleaned_data['source'] == cleaned_data['destination']:
            raise forms.ValidationError("Source and Destination Accounts must differ.")
        return cleaned_data


TransferFormSet = formset_factory(TransferForm, extra=20, can_delete=True,
                                  formset=RequiredInlineFormSet)


class BaseBankForm(forms.ModelForm):
    account = forms.ModelChoiceField(queryset=Account.banks.all())
    amount = forms.DecimalField(min_value=Decimal(".01"),
            widget=forms.TextInput(
                attrs={'size': 10, 'maxlength': 10, 'id': 'entry_amount'}
                )
            )

    def clean_date(self):
        '''The date must be in the Current :class:`FiscalYear`.'''
        date = self.cleaned_data.get('date')
        start = FiscalYear.objects.current_start()
        if start is not None and date < start:
            raise forms.ValidationError("The date must be in the current "
                    "Fiscal Year.")
        return date

    def clean(self):
        '''
        Cleaning the :class:`BaseBankForm` will update or create the
        :attr:`BankSpendingEntry.main_transaction` or
        :attr:`BankReceivingEntry.main_transaction`.
        '''
        super(BaseBankForm, self).clean()
        if any(self.errors):
            return self.cleaned_data
        cleaned_data = self.cleaned_data
        try:
            self.instance.main_transaction.account = cleaned_data['account']
            self.instance.main_transaction.balance_delta = cleaned_data['amount']
            self.instance.main_transaction.detail = cleaned_data['memo']
            self.instance.main_transaction.date = cleaned_data['date']
            cleaned_data['main_transaction'] = self.instance.main_transaction
        except Transaction.DoesNotExist:
            cleaned_data['main_transaction'] = Transaction(
                    account=cleaned_data['account'],
                    balance_delta=cleaned_data['amount'],
                    detail=cleaned_data['memo'],
                    date=cleaned_data['date'])
            self.instance.main_transaction = cleaned_data['main_transaction']
        return cleaned_data

    def save(self, *args, **kwargs):
        '''
        Saving the :class:`BaseBankFormForm` will save both the
        :class:`BaseBankForm` and the
        :attr:`BankSpendingEntry.main_transaction` or
        :attr:`BankReceivingEntry.main_transaction`.
        '''
        self.cleaned_data['main_transaction'].save()
        self.instance.main_transaction = self.cleaned_data['main_transaction']
        super(BaseBankForm, self).save(*args, **kwargs)


@parsleyfy
class BankSpendingForm(BaseBankForm):
    class Meta:
        model = BankSpendingEntry
        fields = ('account', 'date', 'check_number', 'ach_payment', 'payee', 'amount', 'memo',)
        widgets = {'date': forms.DateInput(attrs={'data-americandate': True})}


@parsleyfy
class BankReceivingForm(BaseBankForm):
    class Meta:
        model = BankReceivingEntry
        fields = ('account', 'date', 'payor', 'amount', 'memo',)
        widgets = {'date': forms.DateInput(attrs={'data-americandate': True})}

    def clean_amount(self):
        '''Should be negative(debit) for receiving money'''
        amount = self.cleaned_data.get('amount')
        return -1 * amount


@parsleyfy
class BankTransactionForm(forms.ModelForm):
    amount = forms.DecimalField(max_digits=19, decimal_places=4, min_value=Decimal("0.01"),
                                widget=forms.TextInput(attrs={'size': 10, 'maxlength': 10,
                                                              'class': 'amount'}))

    class Meta:
        model = Transaction
        fields = ('account', 'detail', 'amount', 'event',)
        widgets = {'account': forms.Select(attrs={'class': 'account'})}

    def clean(self):
        super(BankTransactionForm, self).clean()
        if any(self.errors):
            return self.cleaned_data
        cleaned_data = self.cleaned_data
        cleaned_data['balance_delta'] = cleaned_data['amount']
        return cleaned_data


class BaseBankTransactionFormSet(forms.models.BaseInlineFormSet):
    def clean(self):
        '''Checks that Transaction amounts balance Entry amount'''
        super(BaseBankTransactionFormSet, self).clean()
        if any(self.errors):
            return
        balance = abs(self.entry_form.cleaned_data['amount'])
        for form in self.forms:
            if form.cleaned_data.get('DELETE'):
                continue
            balance += -1 * abs(form.cleaned_data.get('amount', 0))
        if balance != 0:
            raise forms.ValidationError("Transactions are out of balance.")

BankSpendingTransactionFormSet = inlineformset_factory(BankSpendingEntry, Transaction,
                                                       form=BankTransactionForm, formset=BaseBankTransactionFormSet,
                                                       extra=5, can_delete=True)

BankReceivingTransactionFormSet = inlineformset_factory(BankReceivingEntry, Transaction,
                                                       form=BankTransactionForm, formset=BaseBankTransactionFormSet,
                                                       extra=5, can_delete=True)


@parsleyfy
class AccountReconcileForm(forms.ModelForm):
    statement_date = forms.DateField(widget=forms.DateInput(attrs={'data-americandate': True}))
    statement_balance = forms.DecimalField()

    class Meta:
        model = Account
        fields = ('statement_date', 'statement_balance')

    def clean_statement_balance(self):
        balance = self.cleaned_data['statement_balance']
        if self.instance.flip_balance():
            balance = -1 * balance
        return balance

    def clean_statement_date(self):
        date = self.cleaned_data['statement_date']
        if (self.instance.last_reconciled is not None and
                date < self.instance.last_reconciled):
            raise forms.ValidationError("Must be later than the Last "
                                        "Reconciled Date")
        return date


class BaseReconcileTransactionFormSet(BaseModelFormSet):
    class Meta:
        model = Transaction

    def clean(self):
        '''Checks that Reconciled Transaction credits/debits balance Statement amount'''
        super(BaseReconcileTransactionFormSet, self).clean()
        if any(self.errors):
            return
        balance = self.account_form.cleaned_data['statement_balance'] - self.reconciled_balance
        for form in self.forms:
            if form.cleaned_data['reconciled']:
                balance += -1 * form.instance.balance_delta
        if balance != 0:
            raise forms.ValidationError("Reconciled Transactions and Bank Statement are out of balance.")

ReconcileTransactionFormSet = modelformset_factory(Transaction, extra=0,
        can_delete=False, fields=('reconciled',), formset=BaseReconcileTransactionFormSet)


@parsleyfy
class FiscalYearForm(forms.ModelForm):
    '''
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
    '''
    class Meta:
        model = FiscalYear
        widgets = {'year': forms.TextInput(attrs={'maxlength': 4, 'size': 4})}

    def clean_year(self):
        '''
        Validates that the entered ``Year`` value is greater than or equal to
        any previously entered ``Year``.
        '''
        year = self.cleaned_data['year']
        max_year = FiscalYear.objects.aggregate(Max('year'))['year__max'] or 0
        if year < max_year:
            raise forms.ValidationError("The Year cannot be before the "
                    "current Year.")
        return year

    def clean(self):
        '''
        Validates that any previous year's ending month is within the entered
        ``Period`` with respect to the entered ``end_month``.

        If the form causes a period change from 13 to 12 months, the method
        will ensure that there are no :class:`Transactions<Transaction>` in the
        13th month of the last :class:`FiscalYear`.

        If there are previous :class:`FiscalYears<FiscalYear>` the method will
        make sure there are both a ``Current Year Earnings`` and
        ``Retained Earnings`` Equity :class:`Accounts<Account>` with an
        :attr:`Account.type` of ``3``.
        '''
        super(FiscalYearForm, self).clean()
        if any(self.errors):
            return self.cleaned_data
        cleaned_data = self.cleaned_data
        if FiscalYear.objects.count() > 0:
            try:
                Account.objects.get(name="Retained Earnings", type=3)
                Account.objects.get(name="Current Year Earnings", type=3)
            except Account.DoesNotExist:
                raise forms.ValidationError("'Current Year Earnings' and "
                        "'Retained Earnings' Equity Accounts are required to "
                        "start a new Fiscal Year.")
            latest = FiscalYear.objects.latest()
            new_date = datetime.date(cleaned_data['year'],
                    cleaned_data['end_month'], 1)
            max_date = latest.date + relativedelta.relativedelta(
                    months=cleaned_data['period'])
            if new_date <= latest.date:
                raise forms.ValidationError("The new ending Date must be "
                        "after the current ending Date.")
            elif new_date > max_date:
                raise forms.ValidationError("The new ending Date cannot be "
                        "greater than the current ending Date plus the new "
                        "Period.")
            if latest.period == 13 and cleaned_data['period'] == 12:
                trans_in_end_month = Transaction.objects.filter(
                        date__year=latest.year,
                        date__month=latest.end_month).exists()
                if trans_in_end_month:
                    raise forms.ValidationError("When switching from a 13 "
                            "month to 12 month period, no Transactions can be "
                            "in  the last Year's 13th month.")
        return cleaned_data


class FiscalYearAccountsForm(forms.ModelForm):
    '''
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

    '''
    exclude = forms.BooleanField(required=False)

    class Meta:
        model = Account

    def __init__(self, *args, **kwargs):
        '''
        Mark an :class:`Account` for exclusion if it has been reconciled.
        '''
        super(FiscalYearAccountsForm, self).__init__(*args, **kwargs)
        self.fields['exclude'].initial = bool(self.instance.last_reconciled)

FiscalYearAccountsFormSet = modelformset_factory(Account, extra=0,
        can_delete=False, fields=('exclude',), form=FiscalYearAccountsForm)
