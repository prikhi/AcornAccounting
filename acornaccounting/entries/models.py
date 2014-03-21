from caching.base import CachingMixin, CachingManager, cached_method
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.db import models
from django.utils import timezone

from fiscalyears.fiscalyears import get_start_of_current_fiscal_year

from .managers import TransactionManager


class BaseJournalEntry(CachingMixin, models.Model):
    """
    Journal Entries group :class:`Transactions<entries.models.Transaction>` by
    discrete points in time.

    For example, a set of transfers, a check being deposited, stipends being
    paid.

    Journal Entries ensure that :class:`Transactions<Transaction>` are
    balanced, that there is an equal amount of credits for every debit.

    .. note::

        This class is an abstract class to prevent multi-table inheritance.

    .. seealso::

        Module :mod:`entries.views`
            Views related to showing, creating and editing Entries.

    .. attribute:: date

        The date the entry occured.

    .. attribute:: memo

        A short description of the Entry.

    .. attribute:: comments

        Any additional comments about the Entry.

    .. attribute:: created_at

        The date and time the Entry was created.

    .. attribute:: updated_at

        The date and time the Entry was last updated. Defaults to
        :attr:`created_at`.

    """
    date = models.DateField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True, default=timezone.now)
    memo = models.CharField(max_length=60)
    comments = models.TextField(blank=True, null=True)

    objects = CachingManager()

    class Meta:
        abstract = True
        ordering = ['date', 'id']
        verbose_name_plural = "journal entries"

    def __unicode__(self):
        return self.memo

    def get_absolute_url(self):
        """Return a link to the Entry's detail page."""
        return reverse('entries.views.show_journal_entry',
                       args=[str(self.id)])

    def get_edit_url(self):
        """Return an edit link to the Entry's edit page."""
        return reverse('entries.views.add_journal_entry', args=[str(self.id)])

    def get_number(self):
        """Return the number of the Entry."""
        return "GJ#{0:06d}".format(self.id)

    def in_fiscal_year(self):
        """
        Determines whether the :attr:`BaseJournalEntry.date` is in the
        current :class:`~fiscalyears.models.FiscalYear`.

        Returns True if there is no current
        :class:`~fiscalyears.models.FiscalYear`.

        :returns: Whether or not the :attr:`date` is in the current
                :class:`~fiscalyears.models.FiscalYear`.
        :rtype: bool

        """
        current_year_start = get_start_of_current_fiscal_year()
        if current_year_start is not None and current_year_start > self.date:
            return False
        return True


class JournalEntry(BaseJournalEntry):
    """A concrete class of the :class:`BaseJournalEntry` model."""
    objects = CachingManager()

    def save(self, *args, **kwargs):
        """Save all related :class:`Transactions<Transaction>` after saving."""
        self.full_clean()
        super(JournalEntry, self).save(*args, **kwargs)
        for transaction in self.transaction_set.all():
            transaction.save()


class BankSpendingEntry(BaseJournalEntry):
    """
    Holds information about a Check or ACH payment for a Bank
    :class:`~accounts.models.Account`. The :attr:`main_transaction` is linked
    to the Bank :class:`~accounts.models.Account`.

    Bank Spending Entries credit the Bank :class:`~accounts.models.Account`
    (via the :attr:`main_transaction`) while debiting all related
    :class:`Transactions<Transaction>`.

    .. attribute:: check_number

        The number of the Check, if applicable. An ACH Payment should have
        no :attr:`check_number` and :attr:`ach_payment` value of ``True`` will
        cause the :attr:`check_number` to be set to ``None``. This value must
        be unique with respect to the
        :attr:`main_transaction's<main_transaction>`
        :class:`account<accounts.models.Account>` attribute.

    .. attribute:: ach_payment

        A boolean representing if this :class:`BankSpendingEntry` is an ACH
        Payment or not. If this is ``True`` the :attr:`check_number` will be
        set to ``None``.

    .. attribute:: payee

        An optional Payee for the :class:`BankSpendingEntry`.

    .. attribute:: void

        A boolean representing whether this :class:`BankSpendingEntry` is void.
        If this value switches from ``False`` to ``True``, all of this
        :class:`BankSpendingEntry's<BankSpendingEntry>`
        :class:`Transactions<Transaction>` will be deleted and it's
        :attr:`main_transaction` will have it's
        :attr:`~Transaction.balance_delta` set to ``0``. Switching void back to
        ``False`` will simply allow transactions to be saved again, it will not
        recreate any previouse :class:`Transactions<Transaction>`.

    .. attribute:: main_transaction

        The :class:`Transaction` that links this :class:`BankSpendingEntry`
        with it's Bank :class:`~accounts.models.Account`.

    """
    # TODO: Change check number to Integer field? Ensure never set to ###ACH###
    check_number = models.CharField(max_length=10, blank=True, null=True)
    ach_payment = models.BooleanField(default=False,
                                      help_text="Invalidates Check Number")
    payee = models.CharField(max_length=20, blank=True, null=True)
    void = models.BooleanField(default=False,
                               help_text="Refunds Associated Transactions.")
    main_transaction = models.OneToOneField('Transaction')

    objects = CachingManager()

    class Meta:
        verbose_name_plural = "bank spending entries"

    def __unicode__(self):
        return self.date.strftime("%d/%m/%y") + " " + self.memo

    def get_absolute_url(self):
        """Return a link to the Entry's detail page."""
        return reverse('entries.views.show_bank_entry',
                       kwargs={'entry_id': str(self.id),
                               'journal_type': 'CD'})

    def get_edit_url(self):
        """Return the Entry's edit URL."""
        return reverse('entries.views.add_bank_entry',
                       args=['CD', str(self.id)])

    def save(self, *args, **kwargs):
        """Delete related Transactions if void, update Transaction dates."""
        # TODO: Should we move this to the base class?
        self.full_clean()
        if self.void:
            [transaction.delete()
             for transaction in self.transaction_set.all()]
            self.main_transaction.balance_delta = 0
            if "VOID" not in self.memo:
                self.memo += " VOID"
        self.main_transaction.date = self.date
        self.main_transaction.save(pull_date=False)
        super(BankSpendingEntry, self).save(*args, **kwargs)
        for transaction in self.transaction_set.all():
            transaction.save()

    def clean(self):
        """
        Only a :attr:`check_number` or an :attr:`ach_payment` must be entered,
        not both.

        The :attr:`check_number` must be unique per
        :attr:`BankSpendingEntry.main_transaction`
        :attr:`Account<Transaction.account>`.

        """
        if not (bool(self.ach_payment) ^ bool(self.check_number)):
            raise ValidationError('Either A Check Number or ACH status is '
                                  'required.')
        super(BankSpendingEntry, self).clean()

    @cached_method
    def get_number(self):
        """Return the formatted :attr:`check_number` or ``##ACH##``."""
        if self.ach_payment:
            return "##ACH##"
        else:
            return "CD#{0:06d}".format(int(self.check_number))


class BankReceivingEntry(BaseJournalEntry):
    """
    Holds information about receiving money for a Bank
    :class:`~accounts.models.Account`. The :attr:`main_transaction` is linked
    to the Bank :class:`~accounts.models.Account`.

    Bank Receiving Entries debit the Bank :class:`~accounts.models.Account`
    (via the :attr:`main_transaction`) while crediting all related
    :class:`Transactions<Transaction>`.

    .. attribute:: payor

        The Person or Company making the payment.

    .. attribute:: main_transaction

        The :class:`Transaction` that links this :class:`BankSpendingEntry`
        with it's Bank :class:`~accounts.models.Account`.
    """
    payor = models.CharField(max_length=50)
    main_transaction = models.OneToOneField('Transaction')

    objects = CachingManager()

    class Meta:
        verbose_name_plural = "bank receiving entries"

    def __unicode__(self):
        return self.memo

    def get_absolute_url(self):
        """Return the Entry's detail page."""
        return reverse('entries.views.show_bank_entry',
                       kwargs={'entry_id': str(self.id),
                               'journal_type': 'CR'})

    def get_edit_url(self):
        """Return the Entry's edit page."""
        return reverse('entries.views.add_bank_entry', args=['CR',
                                                             str(self.id)])

    def save(self, *args, **kwargs):
        """Set the date's of all related :class:`Transactions<Transaction>`."""
        self.full_clean()
        self.main_transaction.date = self.date
        self.main_transaction.save(pull_date=False)
        super(BankReceivingEntry, self).save(*args, **kwargs)
        for transaction in self.transaction_set.all():
            transaction.date = self.date
            transaction.save()

    @cached_method
    def get_number(self):
        """Return the Entry's formatted number."""
        return "CR#{0:06d}".format(self.id)


class Transaction(CachingMixin, models.Model):
    """
    Transactions itemize :class:`~accounts.models.Account` balance changes.

    Transactions are grouped by Entries and
    :class:`Events<events.models.Event>`. Entries group
    :class:`Transactions<Transaction>` by date while
    :class:`Events<events.models.Event>` group by specific events.

    Transactons can be related to Entries through the :attr:`journal_entry`,
    :attr:`bankspend_entry` or :attr:`bankreceive_entry` attributes, or through
    the ``main_transaction`` attribute of the  :class:`BankReceivingEntry` or
    :class:`BankSpendingEntry` models. Transactions may only be related to
    Entries through one of these ways, never multiple ones.

    .. attribute:: journal_entry

        The :class:`JournalEntry` this :class:`Transaction` belongs to, if any.

    .. attribute:: bankspend_entry

        The :class:`BankSpendingEntry` this :class:`Transaction` belongs to, if
        any.

    .. attribute:: bankreceive_entry

        The :class:`BankReceivingEntry` this :class:`Transaction` belongs to,
        if any.

    .. attribute:: account

        The :class:`~accounts.models.Account` this :class:`Transaction` is
        charged to.

    .. attribute:: detail

        Information about the specific charge.

    .. attribute:: balance_delta

        The change in balance this :class:`Transaction` represents. A positive
        value indicates a Credit while a negative value is a Debit.

    .. attribute:: event

        The :class:`~events.models.Event` this Transaction is related to, if
        any.

    .. attribute:: reconciled

        Whether or not this :class:`Transaction` has been marked as Reconciled.

    .. attribute:: date

        The :class:`datetime.date` of the :class:`Transaction`. By default,
        this is automatically pulled from the related Entry when the
        :class:`Transaction` is saved.

    """
    journal_entry = models.ForeignKey(JournalEntry, blank=True, null=True)
    bankspend_entry = models.ForeignKey(BankSpendingEntry, blank=True,
                                        null=True)
    bankreceive_entry = models.ForeignKey(BankReceivingEntry, blank=True,
                                          null=True)
    account = models.ForeignKey('accounts.Account', on_delete=models.PROTECT)
    detail = models.CharField(max_length=50, help_text="Short description of "
                              "the charge", blank=True)
    balance_delta = models.DecimalField(help_text="Positive balance is a "
                                        "credit, negative is a debit",
                                        max_digits=19, decimal_places=4,
                                        db_index=True)
    event = models.ForeignKey('events.Event', blank=True, null=True,
                              on_delete=models.SET_NULL)
    reconciled = models.BooleanField(default=False)
    date = models.DateField(blank=True, null=True, db_index=True)

    objects = TransactionManager()

    class Meta:
        ordering = ['date', 'id']

    def __unicode__(self):
        return self.detail

    def save(self, pull_date=True, *args, **kwargs):
        """Pull the :attr:`date` from the related Entry before saving."""
        self.full_clean()
        if self.get_journal_entry() and pull_date:
            self.date = self.get_journal_entry().date
        super(Transaction, self).save(*args, **kwargs)

    def clean(self):
        """Prevent relations to a void :class:`BankSpendingEntry`."""
        if self.bankspend_entry and self.bankspend_entry.void:
            raise ValidationError("You may not add new Transactions to a void "
                                  "Entry.")

    def get_absolute_url(self):
        """Return a URL to the related Entry's detail page."""
        return self.get_journal_entry().get_absolute_url()

    def get_entry_number(self):
        """Return the related Entry's ``number``."""
        return self.get_journal_entry().get_number()

    def get_final_account_balance(self):
        """
        Return the :class:`Account's<accounts.models.Account>` value balance
        after the Transaction has occured.

        This is accomplished by subtracting the :attr:`balance_delta` of all
        newer :class:`Transactions<Transaction> from the
        :class:`Account's<accounts.models.Account>`
        :attr:`~accounts.models.Account.balance`.

        .. note::

                The value balance is not the same as credit/debit balance. For
                Assets, Liabilities and Equity Accounts, a debit balance means
                a positive value balance instead of the normal negative value
                balance.

        :returns: The :class:`Account's<accounts.models.Account>`
                post-transaction value balance.
        :rtype: :class:`~decimal.Decimal`
        """
        acct_balance = self.account.balance
        # TODO: Refactor query + newer_transactions into manager method
        query = (models.Q(date__gt=self.date) |
                (models.Q(date=self.date) & models.Q(id__gt=self.id)))
        newer_transactions = self.account.transaction_set.filter(
            query).aggregate(models.Sum('balance_delta'))
        acct_balance -= newer_transactions.get('balance_delta__sum') or 0
        if self.account.flip_balance():
            acct_balance *= -1
        return acct_balance

    def get_initial_account_balance(self):
        """Return the value balance of the :class:`~accounts.models.Account`
        from before the Transaction occured.

        :returns: The :class:`Account's<accounts.models.Account>`
                pre-transaction value balance.
        :rtype: :class:`~decimal.Decimal`
        """
        final = self.get_final_account_balance()
        if self.account.flip_balance():
            return final + self.balance_delta
        else:
            return final - self.balance_delta

    def get_journal_entry(self):
        """Return the related Entry."""
        if self.journal_entry:
            return self.journal_entry
        elif self.bankspend_entry:
            return self.bankspend_entry
        elif self.bankreceive_entry:
            return self.bankreceive_entry
        elif (hasattr(self, 'bankreceivingentry') and
              self.bankreceivingentry is not None):
            return self.bankreceivingentry
        elif (hasattr(self, 'bankspendingentry') and
              self.bankspendingentry is not None):
            return self.bankspendingentry

    def get_memo(self):
        """Return  the related Entry's ``memo``."""
        return self.get_journal_entry().memo
