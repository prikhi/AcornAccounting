"""Abstract views used throughout the application."""
from django.contrib import messages
from django.http import Http404
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


def _initialize_entry(request, entry_id, entry_class):
    """Fetch or create a new Entry of entry_class.

    If an entry_id is supplied, the current user must be authenticated.

    """
    if entry_id is not None:
        if not request.user.is_authenticated():
            raise Http404
        entry = get_object_or_404(entry_class, id=entry_id)
    else:
        entry = entry_class()
    return entry


def _create_receipts(valid_form, entry, receipt_class, receipt_entry_field):
    """Create Receipts from the receipts field of a valid form."""
    for receipt in valid_form.cleaned_data['receipts']:
        receipt_class.objects.create(
            **{receipt_entry_field: entry, 'receipt_file': receipt})


def _successful_submission_text(nice_name, entry_form):
    """Generate message text for a successful initial entry submission.

    This function is for Approvable Entries that may contain receipts.

    """
    message_text = ('Your {} Entry has been successfully submitted for '
                    'Approval'.format(nice_name))
    if not entry_form.instance.receipt_set.exists():
        message_text += (
            " Since you did not attach a receipt, <b>you must print this "
            "page</b>, staple your receipts to it and submit the paper "
            "copies to Accounting.")
    return message_text
