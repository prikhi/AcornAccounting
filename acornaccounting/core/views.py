"""Abstract views used throughout the application."""
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
