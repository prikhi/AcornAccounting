import datetime
from decimal import Decimal

from django import forms
from django.forms.models import inlineformset_factory
from .models import Account, JournalEntry, Transaction
from django.forms.formsets import formset_factory
from accounts.models import BankSpendingEntry, BankReceivingEntry


def first_of_month():
    today = datetime.date.today()
    return datetime.date(today.year, today.month, 1).strftime('%m/%d/%Y')


class DateRangeForm(forms.Form):
    startdate = forms.DateField(label="Start Date", initial=first_of_month)
    stopdate = forms.DateField(label="Stop Date", initial=datetime.date.today().strftime('%m/%d/%Y'))


class QuickAccountForm(forms.Form):
    account = forms.ModelChoiceField(queryset=Account.objects.all(),
                                     widget=forms.Select(attrs={'onchange': 'this.form.submit();'}),
                                     label='', empty_label='Jump to an Account')


class JournalEntryForm(forms.ModelForm):
    class Meta:
        model = JournalEntry


class TransactionForm(forms.ModelForm):
    credit = forms.DecimalField(required=False,
                                widget=forms.TextInput(attrs={'size': 10, 'maxlength': 10}))
    debit = forms.DecimalField(required=False,
                                widget=forms.TextInput(attrs={'size': 10, 'maxlength': 10}))

    class Meta:
        model = Transaction
        fields = ('account', 'detail', 'debit', 'credit', 'event',)
        widgets = {'event': forms.TextInput(attrs={'size': 4, 'maxlength': 4})}

    def clean_debit(self):
        '''Makes sure debit is not negative'''
        debit = self.cleaned_data['debit']
        if debit and debit < 0:
            raise forms.ValidationError("Debit cannot be negative.")
        return debit

    def clean_credit(self):
        '''Makes sure credit is not negative'''
        credit = self.cleaned_data.get('credit', None)
        if credit and credit < 0:
            raise forms.ValidationError("Credit cannot be negative.")
        return credit

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


class TransferForm(forms.Form):
    source = forms.ModelChoiceField(queryset=Account.objects.all())
    destination = forms.ModelChoiceField(queryset=Account.objects.all())
    amount = forms.DecimalField(max_digits=19, decimal_places=4, min_value=Decimal("0.01"),
                                widget=forms.TextInput(attrs={'size': 10, 'maxlength': 10}))
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


TransferFormSet = formset_factory(TransferForm, extra=20, can_delete=True)


class BaseBankForm(forms.ModelForm):
    account = forms.ModelChoiceField(queryset=Account.banks.all())
    amount = forms.DecimalField(widget=forms.TextInput(attrs={'size': 10, 'maxlength': 10}),
                                min_value=Decimal(".01"))


class BankSpendingForm(BaseBankForm):
    class Meta:
        model = BankSpendingEntry
        fields = ('account', 'date', 'check_number', 'ach_payment', 'payee', 'amount', 'memo',)


class BankReceivingForm(BaseBankForm):
    class Meta:
        model = BankReceivingEntry
        fields = ('account', 'date', 'payor', 'amount', 'memo',)


class BankTransactionForm(forms.ModelForm):
    amount = forms.DecimalField(max_digits=19, decimal_places=4, min_value=Decimal("0.01"),
                                widget=forms.TextInput(attrs={'size': 10, 'maxlength': 10}))

    class Meta:
        model = Transaction
        fields = ('account', 'detail', 'amount', 'event',)
        widgets = {'event': forms.TextInput(attrs={'size': 4, 'maxlength': 4})}

    def clean(self):
        super(BankTransactionForm, self).clean()
        if any(self.errors):
            return
        cleaned_data = self.cleaned_data
        cleaned_data['balance_delta'] = -1 * cleaned_data['amount']
        return cleaned_data


class BaseBankTransactionFormSet(forms.models.BaseInlineFormSet):
    def clean(self):
        '''Checks that Transaction amounts balance Entry amount'''
        super(BaseBankTransactionFormSet, self).clean()
        if any(self.errors):
            return
        balance = self.entry_form.cleaned_data['amount']
        for form in self.forms:
            balance += -1 * form.cleaned_data.get('amount', 0)
        if balance != 0:
            raise forms.ValidationError("Transactions are out of balance.")
        return self.cleaned_data

BankSpendingTransactionFormSet = inlineformset_factory(BankSpendingEntry, Transaction,
                                                       form=BankTransactionForm, formset=BaseBankTransactionFormSet,
                                                       extra=20, can_delete=True)

BankReceivingTransactionFormSet = inlineformset_factory(BankReceivingEntry, Transaction,
                                                       form=BankTransactionForm, formset=BaseBankTransactionFormSet,
                                                       extra=20, can_delete=True)
