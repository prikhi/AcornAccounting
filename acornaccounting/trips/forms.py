from django import forms
from django.conf import settings
from django.forms.models import inlineformset_factory
from multiupload.fields import MultiFileField
from parsley.decorators import parsleyfy

from core.core import today_in_american_format, remove_trailing_zeroes

from entries.forms import (_set_minimal_queryset_for_account,
                           BaseBankTransactionFormSet)

from .models import TripEntry, TripTransaction, TripStoreTransaction


@parsleyfy
class TripEntryForm(forms.ModelForm):

    """A From for TripEntries along with multiple TripReceipts."""

    receipts = MultiFileField(
        min_num=0, max_num=99, max_file_size=1024 * 1024 * 100, required=False
    )

    class Meta(object):
        model = TripEntry
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'number': forms.TextInput(attrs={'class': 'form-control'}),
            'total_trip_advance': forms.TextInput(
                attrs={'size': 10, 'maxlength': 10, 'class': 'form-control'}),
            'amount': forms.TextInput(
                attrs={'size': 10, 'maxlength': 10, 'class': 'form-control',
                       'id': 'entry_amount'}),
            'comments': forms.Textarea(
                attrs={'rows': 2, 'cols': 50, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        """Set the initial date to today, remove trailing zeros."""
        super(TripEntryForm, self).__init__(*args, **kwargs)
        self.fields['date'].label = "Trip Date"
        if hasattr(self, 'instance') and self.instance.pk:
            formatted_date = self.instance.date.strftime('%m/%d/%Y')
            self.initial['date'] = formatted_date
            trip_advance = self.instance.total_trip_advance
            self.initial['total_trip_advance'] = remove_trailing_zeroes(
                trip_advance)
            amount = self.instance.amount
            self.initial['amount'] = remove_trailing_zeroes(amount)
        else:
            self.initial['date'] = today_in_american_format()


class BaseTripTransactionForm(forms.ModelForm):

    item_price = forms.DecimalField(
        required=False, label='Item Price',
        widget=forms.TextInput(
            attrs={'size': 10, 'maxlength': 10,
                   'class': 'price form-control enter-mod'}))
    tax = forms.DecimalField(
        required=False, initial=settings.DEFAULT_TAX_RATE, label='Tax Rate',
        widget=forms.TextInput(attrs={'size': 4, 'maxlength': 10,
                                      'class': 'tax form-control enter-mod'}))

    def __init__(self, *args, **kwargs):
        super(BaseTripTransactionForm, self).__init__(*args, **kwargs)
        _set_minimal_queryset_for_account(self, 'account')
        amount = self.instance.amount
        if amount is not None:
            self.initial['amount'] = remove_trailing_zeroes(amount)


@parsleyfy
class TripTransactionForm(BaseTripTransactionForm):

    class Meta(object):
        model = TripTransaction
        fields = ('account', 'detail', 'item_price', 'tax', 'amount')
        widgets = {
            'account': forms.Select(
                attrs={'class': 'account account-autocomplete '
                                'form-control enter-mod'}),
            'detail': forms.TextInput(
                attrs={'class': 'form-control enter-mod'}),
            'tax': forms.TextInput(
                attrs={'size': 4, 'maxlength': 4,
                       'class': 'form-control enter-mod'}),
            'amount': forms.TextInput(
                attrs={'size': 10, 'maxlength': 10,
                       'class': 'amount form-control enter-mod'}),
        }


TripTransactionFormSet = inlineformset_factory(
    TripEntry, TripTransaction, form=TripTransactionForm,
    formset=BaseBankTransactionFormSet, extra=10, can_delete=True
)


class TripStoreTransactionForm(BaseTripTransactionForm):

    class Meta(object):
        model = TripStoreTransaction
        fields = ('store', 'account', 'detail', 'item_price', 'tax', 'amount')
        widgets = {
            'store': forms.Select(
                attrs={'class': 'account store form-control enter-mod'}),
            'account': forms.Select(
                attrs={'class': 'account account-autocomplete '
                                'form-control enter-mod'}),
            'detail': forms.TextInput(
                attrs={'class': 'form-control enter-mod'}),
            'tax': forms.TextInput(
                attrs={'size': 4, 'maxlength': 4,
                       'class': 'form-control enter-mod'}),
            'amount': forms.TextInput(
                attrs={'size': 10, 'maxlength': 10,
                       'class': 'amount form-control enter-mod'}),
        }


TripStoreTransactionFormSet = inlineformset_factory(
    TripEntry, TripStoreTransaction, form=TripStoreTransactionForm,
    formset=forms.models.BaseInlineFormSet, extra=2, can_delete=True,
)
