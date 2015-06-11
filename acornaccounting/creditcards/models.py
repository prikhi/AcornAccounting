from django.core.urlresolvers import reverse
from django.db import models
from django.utils import timezone

from accounts.models import (Account)
from core.core import (_american_format)


class CreditCard(models.Model):
    """A Communard-Visible Wrapper for an :class:`~accounts.models.Account`.

    .. attribute:: account

        The :class:`~accounts.models.Account` the CreditCard is linked to. This
        is the Account that will be credited when CreditCardEntries are
        approved.

    .. attribute:: name

        A name for the Credit Card, used in forms accessible by Communards.

    """
    account = models.ForeignKey(Account)
    name = models.CharField(
        max_length=50,
        help_text="A name for Communards. Defaults to the Account's Name.",
        blank=True)

    class Meta(object):
        ordering = ('name',)

    def __unicode__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Pull the name from the Account if blank."""
        if not self.name and self.account:
            self.name = self.account.name
        super(CreditCard, self).save(*args, **kwargs)


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
        return "{} by {}".format(self.card.name, self.name)

    def get_number(self):
        """Generate an Entry number using the id."""
        return "CC#{0:06d}".format(self.id)

    def get_edit_url(self):
        """Return an edit link to the Entry's edit page."""
        return reverse('creditcards.views.add_creditcard_entry',
                       args=[str(self.id)])


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
        max_digits=19, decimal_places=4)

    class Meta(object):
        ordering = ['id']

    def __unicode__(self):
        return "{} - {}".format(self.creditcard_entry.name, self.detail)
