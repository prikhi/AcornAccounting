from django import forms

from .models import Event


class QuickEventForm(forms.Form):
    """
    This form is used to allow selection of a single
    :class:`~events.models.Event`.

    The form will automatically submit when the :class:`~events.models.Event`
    is selected.

    .. seealso::

        View :func:`~events.views.quick_event_search`
            The view this form submits to.

        Method :func:`~accounts.accounting.process_quick_event_form`
            The function responsible for instantiating this class.

        """
    event = forms.ModelChoiceField(
        queryset=Event.objects.all(), label='', empty_label='',
        widget=forms.Select(attrs={'onchange': 'this.form.submit();',
                                   'class': 'form-control autocomplete-select',
                                   'placeholder': 'Jump to an Event'}),
    )
