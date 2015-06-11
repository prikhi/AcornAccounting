from django.db import models

from entries.models import JournalEntry


class Receipt(models.Model):
    """A receipt in the form of a file, linked to JournalEntries.

    .. attribute:: journal_entry

        The :class:`entries.models.JournalEntry` the Receipt is for.

    .. attribute:: receipt_file

        The File containing the Receipt.

    """
    journal_entry = models.OneToOneField(JournalEntry)
    receipt_file = models.FileField(upload_to='uploads/receipts/')

    def __unicode__(self):
        """Use the Journal Entry number & memo to describe the Receipt."""
        return "Receipt for {} - {}".format(
            self.journal_entry.get_number(), self.journal_entry.memo)
