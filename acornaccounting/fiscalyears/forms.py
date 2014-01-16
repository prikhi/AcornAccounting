import datetime

from dateutil import relativedelta
from django import forms
from django.forms.models import modelformset_factory
from parsley.decorators import parsleyfy

from accounts.models import Account
from entries.models import Transaction

from .fiscalyears import get_current_fiscal_year_start
from .models import FiscalYear


@parsleyfy
class FiscalYearForm(forms.ModelForm):
    """
    This form is used to create new
    :class:`Fiscal Years<.models.FiscalYear>`.

    The form validates the period length against the new Fiscal Year's End
    Month and Year. To pass validation, the new Year must be greater than any
    previous years and the end Month must create a period less than or equal to
    the selected Period.

    .. seealso::

        View :func:`~.views.add_fiscal_year`
            The :func:`~.views.add_fiscal_year` view processes all actions
            required for starting a New Fiscal Year.

        Form :class:`FiscalYearAccountsForm`
            This form allows selection of the accounts to exclude in the New
            Fiscal Year's Transaction purging.

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
        current_year = get_current_fiscal_year_start()
        if current_year and new_fiscal_year < current_year.year:
            raise forms.ValidationError("The Year cannot be before the "
                                        "current Year.")
        return new_fiscal_year

    def clean(self):
        """
        Validates that certain :class:`Accounts<accounts.models.Account>` exist
        and that the entered Year is in the allowed range.

        Validates that no previous year's ending month is within the entered
        ``Period`` with respect to the entered ``end_month``.

        If the form causes a period change from 13 to 12 months, the method
        will ensure that there are no
        :class:`Transactions<entries.models.Transaction>` in the 13th month of
        the last :class:`~.models.FiscalYear`.

        If there are previous :class:`FiscalYears<.models.FiscalYear>` the
        method will make sure there are both a ``Current Year Earnings`` and
        ``Retained Earnings`` Equity :class:`Accounts<accounts.models.Account>`
        with a :attr:`~accounts.models.Account.type` of ``3``.

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
    :class:`~entries.models.Transaction` purging caused by the
    :func:`~.views.add_fiscal_year` view.  Selected
    :class:`Accounts<accounts.models.Account>` will retain their unreconciled
    :class:`Transactions<entries.models.Transaction>`.

    This form is used by the :func:`~django.forms.models.modelformset_factory`
    to create the :data:`FiscalYearAccountsFormSet`.

    .. seealso::

        View :func:`~.views.add_fiscal_year`
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

#: An FormSet of :class:`Accounts<accounts.models.Account>` using the
#: :class:`FiscalYearAccountsForm` as the base form.
FiscalYearAccountsFormSet = modelformset_factory(Account, extra=0,
                                                 can_delete=False,
                                                 fields=('exclude',),
                                                 form=FiscalYearAccountsForm)
