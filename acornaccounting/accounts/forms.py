from django import forms
from django.forms.formsets import (INITIAL_FORM_COUNT, TOTAL_FORM_COUNT)
from django.forms.models import (modelformset_factory,
                                 BaseModelFormSet)
from parsley.decorators import parsleyfy

from entries.models import Transaction

from .models import Account


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
        """Convert from a value balance to a credit/debit balance."""
        balance = self.cleaned_data.get('statement_balance')
        if self.instance.flip_balance():
            balance *= -1
        return balance

    def clean_statement_date(self):
        """Ensure the Statement Date is after the Last Reconciled Date."""
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

    def add_form(self, instance):
        """Add a new form instance to a bound Formset."""
        if self.is_bound:
            self.forms.append(self._construct_form(
                self.total_form_count(), instance=instance))
            self.management_form.cleaned_data[INITIAL_FORM_COUNT] += 1
            self.management_form.cleaned_data[TOTAL_FORM_COUNT] += 1


ReconcileTransactionFormSet = modelformset_factory(
    Transaction, extra=0, can_delete=False, fields=('reconciled',),
    formset=BaseReconcileTransactionFormSet)
