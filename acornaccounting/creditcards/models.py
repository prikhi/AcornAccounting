from django.core.files.base import ContentFile
from django.core.urlresolvers import reverse
from django.db import models
from django.utils import timezone

from core.core import _american_format
from core.models import AccountWrapper
from entries.models import JournalEntry, Transaction
from receipts.models import Receipt


class CreditCard(AccountWrapper):
    """A Communard-Visible Wrapper for an :class:`~accounts.models.Account`.

    .. attribute:: account

        The :class:`~accounts.models.Account` the CreditCard is linked to. This
        is the Account that will be credited when CreditCardEntries are
        approved.

    .. attribute:: name

        A name for the Credit Card, used in forms accessible by Communards.

    """


class CreditCardEntry(models.Model):
    """Communard entries used as a pre-approval state for JournalEntries.

    These are used to group together :class:`CreditCardTransactions
    <CreditCardTransaction>` before the Entry is approved by an Accountant.

    When approved, the CreditCardEntry massages it's data into a JournalEntry
    and Transactions so that the relevant Account balances are modified, then
    deletes itself.

    .. attribute:: date

        The date the entry occured.

    .. attribute:: card

        The CreditCard the entry belongs too.

    .. attribute:: name

        The name of the communard who submitted the entry.

    .. attribute:: merchant

        The name of the merchant the purchase was made at.

    .. attribute:: amount

        The total amount of money spent. This is balanced against related
        CreditCardTransactions.

    .. attribute:: comments

        Additional comments from the Communard.

    .. attribute:: created_at

        The date & time the Entry was created.

    """
    date = models.DateField()
    card = models.ForeignKey(CreditCard, verbose_name="Credit Card")
    name = models.CharField(max_length=60)
    merchant = models.CharField(max_length=60)
    amount = models.DecimalField(
        help_text="Positive balance is a charge, negative is a return.",
        verbose_name="Total Amount",
        max_digits=19, decimal_places=4)
    comments = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, default=timezone.now)

    class Meta(object):
        ordering = ('card', 'date', 'created_at',)

    def __unicode__(self):
        return '{} - {} - {}'.format(
            _american_format(self.date), self.name, self.merchant)

    def get_absolute_url(self):
        return reverse('creditcards.views.show_creditcard_entry',
                       args=[str(self.id)])

    def generate_memo(self):
        """Create a memo line from the Entry's attributes."""
        return "{} at {} by {}".format(
            self.card.name, self.merchant, self.name)

    def get_number(self):
        """Generate an Entry number using the id."""
        return "CC#{0:06d}".format(self.id)

    def get_edit_url(self):
        """Return an edit link to the Entry's edit page."""
        return reverse('creditcards.views.add_creditcard_entry',
                       args=[str(self.id)])

    def get_next_entry(self):
        """Return a Queryset of the next possible Entries to display."""
        return CreditCardEntry.objects.filter(
            card=self.card, date__gte=self.date
        ).exclude(pk=self.pk).order_by('date', 'id')

    def approve_entry(self):
        """Creating a JournalEntry Transactions and Receipts from the Entry.

        This does not delete the entry, as should be done when an Entry is
        approved. You **must manually delete** the CreditCardEntry.

        Returns the created JournalEntry.

        """
        journal_entry = JournalEntry.objects.create(
            date=self.date, memo=self.generate_memo(), comments=self.comments)
        transactions = self.transaction_set.all()
        if transactions.count() == 1:
            creditcard_detail = transactions[0].detail
        else:
            creditcard_detail = 'Purchases by {}'.format(self.name)
        for transaction in transactions:
            Transaction.objects.create(
                journal_entry=journal_entry, account=transaction.account,
                detail=transaction.detail,
                balance_delta=(-1 * transaction.amount)
            )
        Transaction.objects.create(
            journal_entry=journal_entry, account=self.card.account,
            balance_delta=self.amount, detail=creditcard_detail,
        )
        for receipt in self.receipt_set.all():
            new_receipt = ContentFile(receipt.receipt_file.file.read())
            new_receipt.name = receipt.receipt_file.name
            Receipt.objects.create(
                journal_entry=journal_entry, receipt_file=new_receipt)

        return journal_entry


class CreditCardTransaction(models.Model):
    """Represents the individual charges for a :class:`CreditCardEntry`.

    Unlike a :class:`entries.models.Transaction`, a CreditCardTransaction does
    not affect the balance of it's :class:`entries.models.Account`.

    .. attribute:: creditcard_entry

        The :class:`CreditCardEntry` the CreditCardTransaction belongs to

    .. attribute:: account

        The related :class:`accounts.models.Account`.

    .. attribute:: detail

        Information about the specific charge.

    .. attribute:: balance_delta

        The change in balance this :class:`Transaction` represents. A positive
        value indicates a Credit while a negative value is a Debit.

    """

    creditcard_entry = models.ForeignKey(
        CreditCardEntry, related_name='transaction_set')
    account = models.ForeignKey(
        'accounts.Account', on_delete=models.PROTECT)
    detail = models.CharField(
        help_text="Short description of the charge", blank=True, max_length=50)
    amount = models.DecimalField(
        help_text="Positive value is a charge, negative is a return",
        verbose_name="Item Amount",
        max_digits=19, decimal_places=4)

    class Meta(object):
        ordering = ['id']

    def __unicode__(self):
        return "{} - {}".format(self.creditcard_entry.name, self.detail)


class CreditCardReceipt(models.Model):
    """Stores Receipts for an unapproved :class:`CreditCardEntry`.

    When the CreditCardEntry is approved, these are turned into
    :class:`receipts.models.Receipts`.

    .. attribute:: receipt_file

        The actual receipt stored as a file.

    .. attribute:: creditcard_entry

        The :class:`CreditCardEntry` this receipt bleongs to.

    """
    creditcard_entry = models.ForeignKey(
        CreditCardEntry, related_name='receipt_set')
    receipt_file = models.FileField(
        blank=True, null=True, upload_to='uploads/unapproved-cc-receipts/')
