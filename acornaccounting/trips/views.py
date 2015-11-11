from django.contrib.auth.decorators import login_required

from core.views import (list_entries, show_single_entry,
                        AddApprovableEntryView)

from .forms import (TripEntryForm, TripTransactionFormSet,
                    TripStoreTransactionFormSet)
from .models import TripEntry, TripReceipt


@login_required
def list_trip_entries(request, template_name='trips/list.html'):
    """Retrieve every :class:`TripEntry`."""
    return list_entries(request, template_name, TripEntry)


def show_trip_entry(request, entry_id, template_name='trips/detail.html'):
    """View a :class:`~.models.TripEntry`."""
    return show_single_entry(request, entry_id, template_name, TripEntry)


def add_trip_entry(request, entry_id=None, template_name='trips/form.html'):
    """Add, edit, approve or delete a :class:`~.models.TripEntry`."""
    view = AddTripEntryView()
    return view.render(request, entry_id, template_name)


class AddTripEntryView(AddApprovableEntryView):
    """Extend the AddApprovableEntryView to apply to TripEntries.

    This view adds an additional formset, the TripStoreTransactionFormSet.

    """

    entry_class = TripEntry
    entry_form_class = TripEntryForm
    transaction_formset_class = TripTransactionFormSet
    verbose_name = 'Trip'
    receipt_class = TripReceipt
    receipt_entry_field = 'trip_entry'
    list_entries_view = 'trips.views.list_trip_entries'
    add_entry_view = 'trips.views.add_trip_entry'
    show_entry_view = 'trips.views.show_trip_entry'

    def __init__(self):
        """Initialize the store_transaction_set variable."""
        super(AddTripEntryView, self).__init__()
        self.store_transaction_formset = None

    def _get_form_initialize(self, request):
        """Initialize the TripStoreTransactionFormSet."""
        super(AddTripEntryView, self)._get_form_initialize(request)
        self.store_transaction_formset = TripStoreTransactionFormSet(
            prefix='store-transaction', instance=self.entry)

    def _post_form_initialize(self, request):
        """Initialize the TripStoreTransactionFormSet."""
        super(AddTripEntryView, self)._post_form_initialize(request)
        self.store_transaction_formset = TripStoreTransactionFormSet(
            request.POST, prefix='store-transaction', instance=self.entry)

    def _forms_valid(self):
        """Check the TripStoreTransactionFormSet as well."""
        return (super(AddTripEntryView, self)._forms_valid() and
                self.store_transaction_formset.is_valid())

    def _post_form_save(self):
        """Save the TripStoreTransactionFormSet as well."""
        super(AddTripEntryView, self)._post_form_save()
        self.store_transaction_formset.save()

    def _make_request_data(self):
        """Include the TripTransactionFormSet in the context."""
        context = super(AddTripEntryView, self)._make_request_data()
        context['store_transaction_formset'] = self.store_transaction_formset
        return context
