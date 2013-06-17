from decimal import Decimal

from caching.base import CachingManager, CachingMixin
from django.contrib.localflavor.us.models import USStateField
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.db import models
from django.utils import timezone
from mptt.models import MPTTModel, TreeForeignKey


class BankAccountManager(models.Manager):
    def get_query_set(self):
        return super(BankAccountManager, self).get_query_set().filter(bank=True)


class TransactionManager(CachingManager):
    '''
    A Custom Manager for the :class:`Transaction` Model

    Subclass of :class:`caching.base.CachingManager`.

    .. note::

        Using this Manager as a Model's default Manager will cause this Manager
        to be used when the Model is accessed through Related Fields.

    '''
    use_for_related_fields = True

    def get_totals(self, query=None, net_change=False):
        '''
        Calculate debit and credit totals for the respective Queryset.

        Groups and Sums the default Queryset by positive/negative :attr:~`Transaction.balance_delta`.
        Totals default to ``0`` if no corresponding :class:`Transaction` is found.

        Optionally:
            * Filters the Manager's Queryset by ``query`` parameter.
            * Returns the Net Change(credits + debits) with the totals.

        :param query: Optional Q query used to filter Manager's Queryset.
        :type query: :class:`~django.db.models.Q` Object.
        :param net_change: Calculate the difference between debits and credits.
        :type net_change: bool.
        :returns: debit and credit sums and optionally net_change.
        :rtype: tuple
        '''
        base_qs = self.get_query_set()
        if query:
            base_qs = base_qs.filter(query)
        debit_total = base_qs.filter(models.Q(balance_delta__lt=0)).        \
            aggregate(models.Sum('balance_delta'))['balance_delta__sum'] or 0
        credit_total = base_qs.filter(models.Q(balance_delta__gt=0)).       \
            aggregate(models.Sum('balance_delta'))['balance_delta__sum'] or 0
        if net_change:
            return debit_total, credit_total, credit_total + debit_total
        return debit_total, credit_total


class BaseAccountModel(CachingMixin, MPTTModel):
    """
    Abstract class storing common attributes of Headers and Accounts
    """
    ASSET = 1
    LIABILITY = 2
    EQUITY = 3
    INCOME = 4
    COST_OF_SALES = 5
    EXPENSE = 6
    OTHER_INCOME = 7
    OTHER_EXPENSE = 8
    TYPE_CHOICES = (
        (ASSET, 'Asset'),
        (LIABILITY, 'Liability'),
        (EQUITY, 'Equity'),
        (INCOME, 'Income'),
        (COST_OF_SALES, 'Cost of Sales'),
        (EXPENSE, 'Expense'),
        (OTHER_INCOME, 'Other Income'),
        (OTHER_EXPENSE, 'Other Expense')
    )

    name = models.CharField(max_length=50, unique=True)
    type = models.PositiveSmallIntegerField(choices=TYPE_CHOICES, blank=True)
    description = models.TextField(blank=True)
    slug = models.SlugField(help_text="Unique identifier used in URL naming",
                            unique=True)

    class Meta:
        abstract = True

    class MPTTMeta:
        order_insertion_by = ['name']

    def flip_balance(self):
        if self.type in (self.ASSET, self.EXPENSE, self.COST_OF_SALES, self.OTHER_EXPENSE):
            return True
        else:
            return False


class Header(BaseAccountModel):
    """
    Groups Accounts Together
    """

    parent = TreeForeignKey('self', blank=True, null=True)
    active = models.BooleanField(default=True)

    objects = CachingManager()

    class Meta:
        ordering = ['name']

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('accounts.views.show_accounts_chart', args=[str(self.slug)])

    def account_number(self):
        tree = self.get_root().get_descendants()
        number = list(tree).index(self) + 1
        return number

    def get_full_number(self):
        """Use type and tree position to generate full account number"""
        full_number = ""
        if self.parent:
            full_number = "{0}-{1:02d}00".format(self.type, self.account_number())
        else:
            full_number = "{0}-0000".format(self.type)
        return full_number
    get_full_number.short_description = "Number"

    def get_account_balance(self):
        ''''Traverses child Headers and Accounts to generate the current balance'''
        balance = Decimal("0.00")
        descendants = self.get_descendants()
        for header in descendants:
            accounts = header.account_set.all()
            for account in accounts:
                balance += account.balance
        for account in self.account_set.all():
            balance += account.balance
        if self.flip_balance():
            balance = -1 * balance
        return balance


class Account(BaseAccountModel):
    """
    Holds information on Accounts
    """
    balance = models.DecimalField(help_text="Positive balance is a credit, negative is a debit",
                                  max_digits=19, decimal_places=4, default="0.00",
                                  editable=False)
    parent = models.ForeignKey(Header)
    active = models.BooleanField(default=True)
    bank = models.BooleanField(default=False, help_text="Adds account to Bank Register")
    last_reconciled = models.DateField(auto_now_add=True)

    objects = CachingManager()
    banks = BankAccountManager()

    class Meta:
        ordering = ['name']

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('accounts.views.show_account_detail', args=[str(self.slug)])

    def account_number(self):
        siblings = self.get_siblings(include_self=True).order_by('name')
        number = list(siblings).index(self) + 1
        return number

    def get_full_number(self):
        """Use parent Header and sibling position to generate full account number"""
        full_number = self.parent.get_full_number()[:-2] + "{0:02d}".format(self.account_number())
        return full_number
    get_full_number.short_description = "Number"

    def get_balance(self):
        if self.flip_balance():
            return self.balance * -1
        else:
            return self.balance


class HistoricalAccount(CachingMixin, models.Model):
    '''
    A model for Archiving Historical Account Data.
    This model is used to store Account balance's and net_changes for each month
    in past :class:`Fiscal Years`.
    Hard data is stored instead of ForeignKeys to other models.

    .. note::

        This model is automatically generated by the :func:`~accounts.views.new_fiscal_year` view.

    .. attribute:: number

        The Account number, formatted as `type-num` must be unique with respect
        to date.

    .. attribute:: name

        The Account's name, must be unique with respect to date.

    .. attribute:: type

        The Account's type, chosen from :attr:`~BaseAccountModel.TYPE_CHOICES`.

    .. attribute:: amount

        The end-of-month Account balance or net change (for types 1-3, 4-8
        respectively).

    .. attribute:: date

        A :class:`datetime.date` object representing the 1st day of the Month and Year the
        archive was created.
    '''
    number = models.CharField(max_length=6)
    name = models.CharField(max_length=50)
    type = models.PositiveSmallIntegerField(choices=BaseAccountModel.TYPE_CHOICES)
    amount = models.DecimalField(max_digits=19, decimal_places=4)
    date = models.DateField()

    objects = CachingManager()

    class Meta:
        ordering = ['date', 'number']
        unique_together = ('date', 'name')

    def __unicode__(self):
        return '{0}/{1} - {2}'.format(self.date.year, self.date.month, self.name)

    def get_absolute_url(self):
        '''
        The default URL for HistoricalAccounts points to the listing for the
        ``dates`` ``month`` and ``year``.
        '''
        return reverse('accounts.views.show_account_history',
                       kwargs={'month': self.date.month, 'year': self.date.year})


class BaseJournalEntry(CachingMixin, models.Model):
    """
    Groups a series of Transactions together
    """
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True, default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True, default=timezone.now)
    memo = models.CharField(max_length=60)

    objects = CachingManager()

    class Meta:
        abstract = True
        verbose_name_plural = "journal entries"
        ordering = ['date', 'id']

    def __unicode__(self):
        return self.memo

    def get_absolute_url(self):
        return reverse('accounts.views.show_journal_entry', args=[str(self.id)])

    def get_edit_url(self):
        return reverse('accounts.views.add_journal_entry', args=[str(self.id)])

    def get_number(self):
        return "GJ#{0:06d}".format(self.id)


class JournalEntry(BaseJournalEntry):
    def save(self, *args, **kwargs):
        self.full_clean()
        super(BaseJournalEntry, self).save(*args, **kwargs)
        for transaction in self.transaction_set.all():
            transaction.date = self.date
            transaction.save()


class BankSpendingEntry(BaseJournalEntry):
    '''
    Holds information about a Check or ACH payment for a Bank
    :class:`Account`. The :attr:`main_transaction` is linked to a Bank
    :class:`Account`.

    .. attribute:: check_number

        The number of the Check, if applicable. An ACH Payment should have
        no :attr:`check_number` and and :attr:`ach_payment` value of ``True``
        will cause the :attr:`check_number` to be set to ``None``. This value
        must be unique with respect to the
        :attr:`main_transaction's<main_transaction>` :class:`account<Account>`
        attribute.

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
        :attr:`~Transaction.balance_delta` set to ``0``.

    .. attribute:: main_transaction

        The :class:`Transaction` that links this :class:`BankSpendingEntry`
        with it's Bank :class:`Account`.
    '''
    check_number = models.CharField(max_length=10, blank=True, null=True)
    ach_payment = models.BooleanField(default=False, help_text="Invalidates Check Number")
    payee = models.CharField(max_length=20, blank=True, null=True)
    void = models.BooleanField(default=False, help_text="Refunds Associated Transactions.")
    main_transaction = models.OneToOneField('Transaction')

    class Meta:
        verbose_name_plural = "bank spending entries"
        ordering = ['date', 'id']

    def __unicode__(self):
        return self.memo

    def get_absolute_url(self):
        return reverse('accounts.views.show_bank_entry',
                kwargs={'journal_id': str(self.id),
                        'journal_type': 'CD'})

    def save(self, *args, **kwargs):
        self.full_clean()
        self.main_transaction.date = self.date
        self.main_transaction.save(pull_date=False)
        super(BankSpendingEntry, self).save(*args, **kwargs)
        for transaction in self.transaction_set.all():
            transaction.date = self.date
            transaction.save()

    def clean(self):
        '''
        Either a :attr:`check_number` xor an :attr:`ach_payment` is required.

        The :attr:`check_number` must be unique per :attr:`BankSpendingEntry.main_transaction`
        :attr:`~Transaction.account`.
        '''
        if not (bool(self.ach_payment) ^ bool(self.check_number)):
            raise ValidationError('Either A Check Number or ACH status is '
                    'required.')
        same_check_number = BankSpendingEntry.objects.filter(
                main_transaction__account=self.main_transaction.account,
                check_number=self.check_number).exclude(id=self.id).exists()
        if self.check_number is not None and same_check_number:
            raise ValidationError('The check number must be unique per Bank '
                    'Account.')
        super(BankSpendingEntry, self).clean()

    def get_edit_url(self):
        return reverse('accounts.views.add_bank_entry', args=['CD', str(self.id)])

    def get_number(self):
        if self.ach_payment:
            return "##ACH##"
        else:
            return "CD#{0:06d}".format(int(self.check_number))


class BankReceivingEntry(BaseJournalEntry):
    payor = models.CharField(max_length=50)
    main_transaction = models.OneToOneField('Transaction')

    class Meta:
        verbose_name_plural = "bank receiving entries"
        ordering = ['date', 'id']

    def __unicode__(self):
        return self.memo

    def get_absolute_url(self):
        return reverse('accounts.views.show_bank_entry', kwargs={'journal_id': str(self.id),
                                                                 'journal_type': 'CR'})

    def save(self, *args, **kwargs):
        self.full_clean()
        self.main_transaction.date = self.date
        self.main_transaction.save(pull_date=False)
        super(BankReceivingEntry, self).save(*args, **kwargs)
        for transaction in self.transaction_set.all():
            transaction.date = self.date
            transaction.save()

    def get_edit_url(self):
        return reverse('accounts.views.add_bank_entry', args=['CR', str(self.id)])

    def get_number(self):
        return "CR#{0:06d}".format(self.id)


class Transaction(CachingMixin, models.Model):
    """
    Holds information about a single Transaction
    """
    journal_entry = models.ForeignKey(JournalEntry, blank=True, null=True)
    bankspend_entry = models.ForeignKey(BankSpendingEntry, blank=True, null=True)
    bankreceive_entry = models.ForeignKey(BankReceivingEntry, blank=True, null=True)
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    detail = models.CharField(max_length=50, help_text="Short description", blank=True)
    balance_delta = models.DecimalField(help_text="Positive balance is a credit, negative is a debit",
                                        max_digits=19, decimal_places=4)
    event = models.ForeignKey('Event', blank=True, null=True)
    reconciled = models.BooleanField(default=False)
    date = models.DateField(blank=True, null=True)

    objects = TransactionManager()

    class Meta:
        ordering = ['date', 'id']

    def __unicode__(self):
        return self.detail

    def save(self, pull_date=True, *args, **kwargs):
        self.full_clean()
        if self.get_journal_entry() and pull_date:
            self.date = self.get_journal_entry().date
        super(Transaction, self).save(*args, **kwargs)

    def get_absolute_url(self):
        return self.get_journal_entry().get_absolute_url()

    def get_date(self):
        return self.get_journal_entry().date

    def get_entry_number(self):
        return self.get_journal_entry().get_number()

    def get_final_account_balance(self):
        """Returns Account balance after transaction has occured."""
        date = self.date
        acct_balance = self.account.balance
        query = (models.Q(date__gt=date) |
                (models.Q(date=date) & models.Q(id__gt=self.id)))
        newer_transactions = self.account.transaction_set.filter(query)
        for transaction in newer_transactions:
            acct_balance += (-1 * (transaction.balance_delta))
        if self.account.flip_balance():
            acct_balance = -1 * acct_balance
        return acct_balance

    def get_initial_account_balance(self):
        final = self.get_final_account_balance()
        if self.account.flip_balance():
            return final + self.balance_delta
        else:
            return final - self.balance_delta

    def get_journal_entry(self):
        if self.journal_entry:
            return self.journal_entry
        elif self.bankspend_entry:
            return self.bankspend_entry
        elif self.bankreceive_entry:
            return self.bankreceive_entry
        elif hasattr(self, 'bankreceivingentry'):
            return self.bankreceivingentry
        elif hasattr(self, 'bankspendingentry'):
            return self.bankspendingentry

    def get_memo(self):
        return self.get_journal_entry().memo


class Event(models.Model):
    '''
    Hold information about Events
    '''
    name = models.CharField(max_length=150)
    number = models.PositiveIntegerField()
    date = models.DateField()
    city = models.CharField(max_length=50)
    state = USStateField()

    class Meta:
        ordering = ['date']

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('accounts.views.show_event_detail',
                       kwargs={'event_id': self.id})
