from django.core.files.base import ContentFile
from django.core.urlresolvers import reverse
from django.db import models
from django.utils import timezone

from accounts.models import Account
from core.models import AccountWrapper
from entries.models import JournalEntry, Transaction
from receipts.models import Receipt


class StoreAccount(AccountWrapper):
    """A Communard-visible Wrapper for an :class:`~accounts.models.Account`.

    This is used to allow Communards to select an Account for purchases made on
    store credit.

    """


class TripEntry(models.Model):
    """Communard entries used as a pre-approval state for JournalEntries.

    These are used to group together in-town purchases by Communards before the
    Entry is approved by an Accountant.

    When approved, the TripEntry massages it's data into a JournalEntry and
    Transactions so that the relevant Account balances are actually modified,
    then the TripEntry deletes itself.

    """
    date = models.DateField()
    name = models.CharField(max_length=60)
    number = models.CharField(max_length=15)
    total_trip_advance = models.DecimalField(
        max_digits=19, decimal_places=4, verbose_name='Total Trip Advance')
    amount = models.DecimalField(
        max_digits=19, decimal_places=4, verbose_name='Cash Spent')
    comments = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, default=timezone.now)

    class Meta(object):
        ordering = ('date', 'number', 'name',)

    def __unicode__(self):
        return 'TJ#{} by {}'.format(self.number, self.name)

    def get_absolute_url(self):
        return reverse('trips.views.show_trip_entry', args=[str(self.id)])

    def get_edit_url(self):
        return reverse('trips.views.add_trip_entry', args=[str(self.id)])

    def generate_memo(self):
        return "{}'s Trip {}".format(self.name, self.number)

    def get_number(self):
        """Generate an Entry Number using the number attribute."""
        return 'TJ#{}'.format(self.number)

    def get_next_entry(self):
        """Return the next Entry for Editing/Approval."""
        this_date = TripEntry.objects.filter(
            id__gt=self.id, date=self.date).order_by('id')
        return this_date if this_date.exists() else TripEntry.objects.filter(
            date__gt=self.date).order_by('date', 'id')

    def approve_entry(self):
        """Creating a JournalEntry Transactions and Receipts from the Entry.

        This does not delete the entry, as should be done when an Entry is
        approved. You **must manually delete** the TripEntry.

        Returns the created JournalEntry.

        """
        journal_entry = JournalEntry.objects.create(
            date=self.date, memo=self.generate_memo(),
            comments=self.comments)
        trip_advance_account = Account.objects.get(name='Trip Advances')
        for transaction in self.transaction_set.all():
            Transaction.objects.create(
                journal_entry=journal_entry, account=transaction.account,
                detail=transaction.detail,
                balance_delta=(-1 * transaction.amount)
            )
        Transaction.objects.create(
            journal_entry=journal_entry, account=trip_advance_account,
            balance_delta=self.amount
        )
        for transaction in self.store_transaction_set.all():
            Transaction.objects.create(
                journal_entry=journal_entry, account=transaction.account,
                detail=transaction.detail,
                balance_delta=(-1 * transaction.amount)
            )
            Transaction.objects.create(
                journal_entry=journal_entry, account=transaction.store.account,
                detail=transaction.detail, balance_delta=transaction.amount
            )

        for receipt in self.receipt_set.all():
            new_receipt = ContentFile(receipt.receipt_file.file.read())
            new_receipt.name = receipt.receipt_file.name
            Receipt.objects.create(
                journal_entry=journal_entry, receipt_file=new_receipt)
        return journal_entry


class TripTransaction(models.Model):
    """Represents the individual charges/returns for a :class:`TripEntry`.

    The creation of a TripTransaction does not affect Account balances, this
    only occurs when the related TripEntry is approved - by removing the
    TripEntry and TripTransactions and creating a JournalEntry and
    Transactions.

    """
    trip_entry = models.ForeignKey(
        TripEntry, related_name='transaction_set',
    )
    account = models.ForeignKey('accounts.Account', on_delete=models.PROTECT)
    detail = models.CharField(
        help_text='Short description of the charge', blank=True, max_length=50,
    )
    amount = models.DecimalField(
        help_text="Positive value is a charge, negative is a return",
        verbose_name="Total Item Amount", max_digits=19, decimal_places=4,
    )

    class Meta(object):
        ordering = ['trip_entry', 'id']

    def __unicode__(self):
        return "{} - {}".format(self.trip_entry.name, self.detail)


class TripStoreTransaction(models.Model):
    """Represents a purchase at a StoreAccount for a :class:`TripEntry`."""
    trip_entry = models.ForeignKey(
        TripEntry, related_name='store_transaction_set')
    store = models.ForeignKey(StoreAccount, on_delete=models.PROTECT)
    account = models.ForeignKey('accounts.Account', on_delete=models.PROTECT)
    detail = models.CharField(
        help_text='Short description of the charge', blank=True, max_length=50,
    )
    amount = models.DecimalField(
        help_text="Positive value is a charge, negative is a return",
        verbose_name="Total Item Amount", max_digits=19, decimal_places=4,
    )

    class Meta(object):
        ordering = ['trip_entry', 'id']

    def __unicode__(self):
        return "{} - {} - {}".format(
            self.trip_entry.name, self.store, self.detail)


class TripReceipt(models.Model):
    """Stores Receipts for an unapproved :class:`TripEntry`."""
    trip_entry = models.ForeignKey(TripEntry, related_name='receipt_set',)
    receipt_file = models.FileField(
        blank=True, null=True, upload_to='uploads/unapproved-trip-receipts/')
