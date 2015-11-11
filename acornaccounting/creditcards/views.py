from django.contrib.auth.decorators import login_required

from core.views import (list_entries, show_single_entry,
                        AddApprovableEntryView)

from .forms import CreditCardEntryForm, CreditCardTransactionFormSet
from .models import CreditCardEntry, CreditCardReceipt


@login_required
def list_creditcard_entries(request, template_name='creditcards/list.html'):
    """Retrieve every :class:`CreditCardEntry`."""
    return list_entries(request, template_name, CreditCardEntry)


def show_creditcard_entry(request, entry_id,
                          template_name="creditcards/show_entry.html"):
    """View a :class:`~.models.CreditCardEntry`."""
    return show_single_entry(request, entry_id, template_name, CreditCardEntry)


def add_creditcard_entry(request, entry_id=None,
                         template_name="creditcards/credit_card_form.html"):
    """Add, edit, approve or delete a :class:`~.models.CreditCardEntry`."""
    view = AddCreditCardEntry()
    return view.render(request, entry_id, template_name)


class AddCreditCardEntry(AddApprovableEntryView):
    """Customize the generic AddApprovableEntryView for CreditCardEntries."""
    entry_class = CreditCardEntry
    entry_form_class = CreditCardEntryForm
    transaction_formset_class = CreditCardTransactionFormSet
    verbose_name = 'Credit Card'
    receipt_class = CreditCardReceipt
    receipt_entry_field = 'creditcard_entry'
    list_entries_view = 'creditcards.views.list_creditcard_entries'
    add_entry_view = 'creditcards.views.add_creditcard_entry'
    show_entry_view = 'creditcards.views.show_creditcard_entry'
