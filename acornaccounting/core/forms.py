from django import forms

from parsley.decorators import parsleyfy


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
    """A form for acquiring a DateRange via a start_date and enddate."""
    start_date = forms.DateField(label="Start Date",
                                 widget=forms.DateInput(
                                     attrs={'data-americandate': True,
                                            'size': 8,
                                            'class': 'form-control'})
                                 )
    stop_date = forms.DateField(label="Stop Date",
                                widget=forms.DateInput(
                                    attrs={'data-americandate': True,
                                           'size': 8,
                                           'class': 'form-control'})
                                )
