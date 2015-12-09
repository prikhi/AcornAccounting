"""Abstract views used throughout the application."""
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render, get_object_or_404


def list_entries(request, template_name, entry_class):
    """Return a response for listing all specified Entries."""
    entries = entry_class.objects.all()
    return render(request, template_name, {'entries': entries})


def show_single_entry(request, entry_id, template_name, entry_class):
    """View single Entry, specified by id and class."""
    entry = get_object_or_404(entry_class, pk=entry_id)
    return render(request, template_name,
                  {'journal_entry': entry,
                   'transactions': entry.transaction_set.all()})


class AddApprovableEntryView(object):
    """A View for adding, editing, approving and deleting Approvable Entries

    To use this view, subclass it and set the following class attributes:

        * entry_class - The class of the Approvable Entry
        * entry_form_class - The class of the Entry's Form
        * transaction_formset_class - The class of the Entry's Transaction's
          FormSet
        * verbose_name - A user-friendly name for the Entry type
        * receipt_class - The class of the Entry's Receipts
        * receipt_entry_field - The field to access an Entry from a Receipt
        * list_entries_view - The view used to list all Entries(a string of the
          module-dotted path for use with reverse, e.g.
          ``trips.views.list_trip_entries``)
        * add_entry_view - The view used to add a new Entry
        * show_entry_view - The view used to show a single Entry.

    The Entry must have the following methods defined:

        * entry.get_number() - Produces a journal number like XX#000123
        * entry.approve_entry() - Creates a JournalEntry, Transactions and
          Receipts from the Entry. Should not delete the Entry.
        * entry.get_next_entry() - Produces a Queryset of the Entries to fetch
          next, if any exist.

    The following instance variables are set during request processing:

        * entry - The model instance being created/modified.
        * entry_form - The bound form
        * transaction_formset - The bound formset

    """

    entry_class = entry_form_class = transaction_formset_class = None
    verbose_name = receipt_class = list_entries_view = add_entry_view = None
    show_entry_view = None

    def __init__(self):
        """Set instance variables to None."""
        self.entry = self.entry_form = self.transaction_formset = None

    def render(self, request, entry_id, template_name):
        """Use the specified class attributes to render the view."""
        assert None not in [
            self.entry_class, self.entry_form_class, self.verbose_name,
            self.transaction_formset_class, self.receipt_class,
            self.list_entries_view, self.add_entry_view, self.show_entry_view,
        ], 'A required class attribute has not been set'
        self._initialize_entry(request, entry_id)
        if request.method == 'POST':
            return self._post(request, entry_id, template_name)
        else:
            return self._get(request, template_name)

    def _initialize_entry(self, request, entry_id):
        """Fetch or create a new Entry of entry_class."""
        if entry_id is not None:
            if not request.user.is_authenticated():
                raise Http404
            self.entry = get_object_or_404(self.entry_class, id=entry_id)
        else:
            self.entry = self.entry_class()

    def _get(self, request, template_name):
        """Handle a GET request."""
        self._get_form_initialize(request)
        data = self._make_request_data()
        return render(request, template_name, data)

    def _get_form_initialize(self, request):
        """Initialize the forms during a POST request."""
        self.entry_form = self.entry_form_class(
            prefix='entry', instance=self.entry)
        self.transaction_formset = self.transaction_formset_class(
            prefix='transaction', instance=self.entry)
        self.transaction_formset.entry_form = self.entry_form

    def _post(self, request, entry_id, template_name):
        """Handle a POST request."""
        self._post_form_initialize(request)
        submision_type = (
            request.POST.get('subbtn', request.POST.get('delete', '')).lower())
        if any(t in submision_type for t in ['submit', 'approve']):
            if self._forms_valid():
                self._post_form_save()
                if 'approve' in submision_type:
                    return self._approve_and_redirect(
                        request, 'next' in submision_type)
                if entry_id is None:
                    messages.success(
                        request, self._successful_submission_text())
                else:
                    messages.success(
                        request, self._successful_edit_text())
                return self._redirect(request, submision_type)
        elif 'delete' in submision_type and self.entry.pk:
            self.entry.delete()
            messages.success(
                request, 'The {} Entry was successfully deleted.'.format(
                    self.verbose_name))
            return HttpResponseRedirect(reverse(self.list_entries_view))
        else:
            raise Http404
        data = self._make_request_data()
        return render(request, template_name, data)

    def _post_form_initialize(self, request):
        """Initialize the forms during a POST request."""
        self.entry_form = self.entry_form_class(
            request.POST, request.FILES, prefix='entry', instance=self.entry)
        self.transaction_formset = self.transaction_formset_class(
            request.POST, prefix='transaction', instance=self.entry)
        self.transaction_formset.entry_form = self.entry_form

    def _forms_valid(self):
        """Check if all forms are valid."""
        return (self.entry_form.is_valid() and
                self.transaction_formset.is_valid())

    def _post_form_save(self):
        """Save the forms and create any Receipts."""
        self.entry_form.save()
        self.transaction_formset.save()
        self._create_receipts()

    def _create_receipts(self):
        """Create Receipts from the receipts field of the form."""
        for receipt in self.entry_form.cleaned_data['receipts']:
            self.receipt_class.objects.create(
                **{self.receipt_entry_field: self.entry,
                   'receipt_file': receipt})

    def _approve_and_redirect(self, request, redirect_to_next):
        """Approve the Entry and redirect to the proper page."""
        journal_entry = self.entry.approve_entry()
        messages.success(request, (
            "Approved the {} Entry & Created <a href='{}' "
            "target='_blank'>{}</a>.".format(
                self.verbose_name, journal_entry.get_absolute_url(),
                journal_entry.get_number())))
        redirect_url = None
        if redirect_to_next:
            next_entry = self.entry.get_next_entry()
            if next_entry.exists():
                redirect_url = reverse(
                    self.add_entry_view, args=[str(next_entry[0].id)])
        if redirect_url is None:
            redirect_url = reverse(self.list_entries_view)
        self.entry.delete()
        return HttpResponseRedirect(redirect_url)

    def _redirect(self, request, submision_type):
        """Redirect a Communard after submitting an Entry."""
        if 'add more' in submision_type:
            if not self.entry.receipt_set.exists():
                messages.warning(
                    request,
                    "You did not attach a receipt, you <b>must</b> print this "
                    "page & submit it to Accounting along with a hardcopy of "
                    "the receipt.")
                return HttpResponseRedirect(
                    reverse(self.show_entry_view, args=[str(self.entry.id)]))
            return HttpResponseRedirect(reverse(self.add_entry_view))
        elif 'next' in submision_type:
            next_entry = self.entry.get_next_entry()
            if next_entry.exists():
                return HttpResponseRedirect(
                    reverse(self.add_entry_view,
                            kwargs={'entry_id': next_entry[0].id}))
            else:
                return HttpResponseRedirect(reverse(self.list_entries_view))
        return HttpResponseRedirect(
            reverse(self.show_entry_view, kwargs={'entry_id': self.entry.id}))

    def _successful_submission_text(self):
        """Generate message text for a successful initial entry submission."""
        message_text = ('Your {} Entry has been successfully submitted for '
                        'Approval.'.format(self.verbose_name))
        if not self.entry_form.instance.receipt_set.exists():
            message_text += (
                " Since you did not attach a receipt, <b>you must print this "
                "page</b>, staple your receipts to it and submit the paper "
                "copies to Accounting.")
        return message_text

    def _successful_edit_text(self):
        """Generate message text for a successful entry update."""
        return "Modified Entry <a href='{}' target='_blank'>{}</a>.".format(
            self.entry.get_absolute_url(), self.entry.get_number())

    def _make_request_data(self):
        """Create the context data for the template."""
        return {'entry_form': self.entry_form,
                'transaction_formset': self.transaction_formset,
                'verbose_entry_type': '{} Entry'.format(self.verbose_name)}
