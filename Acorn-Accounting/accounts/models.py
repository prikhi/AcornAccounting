import calendar
import datetime
from dateutil import relativedelta
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
            aggregate(models.Sum('balance_delta'))['balance_delta__sum'] or Decimal(0)
        credit_total = base_qs.filter(models.Q(balance_delta__gt=0)).       \
            aggregate(models.Sum('balance_delta'))['balance_delta__sum'] or Decimal(0)
        if net_change:
            return debit_total, credit_total, credit_total + debit_total
        return debit_total, credit_total


class FiscalYearManager(CachingManager):
    '''
    A Custom Manager for the :class:`FiscalYear` model.
    '''
    def current_start(self):
        '''
        Determine the Start Date of the Latest :class:`FiscalYear`.

        If there are no :class:`FiscalYears<FiscalYear>` then this method will
        return ``None``.

        If there is one :class:`FiscalYear` then the starting date will be the
        :attr:`~FiscalYear.period` amount of months before it's
        :attr:`~FiscalYear.date`.

        If there are multiple :class:`FiscalYears<FiscalYear>` then the first
        day and month after the Second Latest :class:`FiscalYear` will be
        returned.

        :returns: The starting date of the current :class:`FiscalYear`.
        :rtype: :class:`datetime.date` or None
        '''
        if FiscalYear.objects.exists():
            if FiscalYear.objects.count() > 1:
                second_latest = FiscalYear.objects.order_by('-date')[1]
                return second_latest.date + relativedelta.relativedelta(
                        months=1)
            else:
                current_year = FiscalYear.objects.get()
                return current_year.date - relativedelta.relativedelta(
                        months=current_year.period - 1)
        else:
            return None


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
    last_reconciled = models.DateField(null=True, blank=True)

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

    def get_balance_by_date(self, date):
        '''
        Calculates the :class:`Accounts<Account>` balance on a specific
        ``date``.

        :param date: The day whose balance should be returned.
        :type date: datetime.date
        :returns: The Account's balance on a specified date.
        :rtype: decimal.Decimal
        '''
        transactions = self.transaction_set.filter(
                date__lte=date).order_by('-date', '-id')
        if transactions.exists():
            return transactions[0].get_final_account_balance()
        else:
            return Decimal(0)

    def get_balance_change_by_month(self, date):
        '''
        Calculates the :class:`Accounts<Account>` net change in balance for the
        specified ``date``.

        :param date: The month to calculate the net change for.
        :type date: datetime.date
        :returns: The Account's net balance change for the specified month.
        :rtype: decimal.Decimal
        '''
        days_in_month = calendar.monthrange(date.year, date.month)[1]
        firstday = datetime.date(date.year, date.month, 1)
        lastday = datetime.date(date.year, date.month, days_in_month)
        query = (models.Q(date__gte=firstday, date__lte=lastday) &
                 models.Q(account__id=self.id))
        (_, _, net_change) = Transaction.objects.get_totals(query, True)
        if self.flip_balance():
            net_change *= -1
        return net_change


class HistoricalAccount(CachingMixin, models.Model):
    '''
    A model for Archiving Historical Account Data.
    It stores an :class:`Account's<Account>` balance or net_change for a
    certain month in a previous :class:`Fiscal Years`.

    Hard data is stored in additon to a link back to the originating
    :class:`Account`.

    .. note::

        This model is automatically generated by the
        :func:`~accounts.views.add_fiscal_year` view.

    .. note::

        This model does not inherit from the :class:`BaseAccountModel`
        because it has no ``parent`` attribute and cannot inherit from
        :class:`MPTTModel`.

    .. attribute:: account

        The :class:`Account` this HistoricalAccount was generated for. The
        HistoricalAccount will remain even if the :class:`Account` is deleted.

    .. attribute:: number

        The Account number, formatted as `type-num` must be unique with respect
        to date.

    .. attribute:: name

        The Account's name, must be unique with respect to date.

    .. attribute:: type

        The Account's type, chosen from :attr:`~BaseAccountModel.TYPE_CHOICES`.

    .. attribute:: amount

        The end-of-month balance for
        :class:`HistoricalAccounts<HistoricalAccount>` with :attr:`type` 1-3,
        and the net change for :class:`HistoricalAccounts<HistoricalAccount>`
        with :attr:`type` 4-8. This field represents the credit/debit amount
        not the value amount. To retrieve the value amount for a
        :class:`HistoricalAccount` use the :meth:`get_amount` method.

    .. attribute:: date

        A :class:`datetime.date` object representing the 1st day of the Month and Year the
        archive was created.
    '''
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, blank=True, null=True)
    number = models.CharField(max_length=6)
    name = models.CharField(max_length=50)
    type = models.PositiveSmallIntegerField(choices=BaseAccountModel.TYPE_CHOICES)
    amount = models.DecimalField(max_digits=19, decimal_places=4)
    date = models.DateField()

    objects = CachingManager()

    class Meta:
        ordering = ['date', 'number']
        get_latest_by = ('date', )
        unique_together = ('date', 'name')

    def __unicode__(self):
        return '{0}/{1} - {2}'.format(self.date.year, self.date.month, self.name)

    def get_absolute_url(self):
        '''
        The default URL for a HistoricalAccount points to the listing for the
        :attr:`date's<date>` ``month`` and ``year``.
        '''
        return reverse('accounts.views.show_account_history',
                       kwargs={'month': self.date.month, 'year': self.date.year})

    def get_amount(self):
        '''
        Calculates the flipped/value ``balance`` or ``net_change`` for Asset,
        Cost of Sales, Expense and Other Expense
        :class:`HistoricalAccounts<HistoricalAccount>`.

        The :attr:`amount` field for
        :class:`HistoricalAccounts<HistoricalAccount>` represents the
        credit/debit amounts but debits for Asset, Cost of Sales, Expense
        and Other Expenses represent a positive value instead of a negative
        value. This function returns the value amount of these accounts instead
        of the debit/credit amount. E.g., a negative(debit) amount will be
        returned as a positive value amount.

        If the :class:`HistoricalAccount` is not one of these types, the
        :class:`HistoricalAccounts<HistoricalAccount>` normal :attr:`amount`
        will be returned.

        :returns: The value :attr:`amount` for the :class:`HistoricalAccount`
        :rtype: :class:`decimal.Decimal`
        '''
        if self.flip_balance():
            return self.amount * -1
        else:
            return self.amount

    def flip_balance(self):
        '''
        Determines whether the :attr:`HistoricalAccount.amount` should be
        flipped based on the :attr:`HistoricalAccount.type`.

        For example, debits(negative :attr:`HistoricalAccount.amount`) increase
        the value of Assets, Expenses, Cost of Sales and Other Expenses, while
        decreasing the value of all other
        :attr:`Account Types<BaseAccountModel.TYPE_CHOICES>`.

        In essence, this method will return ``True`` if the credit/debit amount
        needs to be flipped(multiplied by -1) to display the value amount, and
        ``False`` if the credit/debit amount is the displayable value amount.
        '''
        if self.type in (BaseAccountModel.ASSET, BaseAccountModel.EXPENSE,
                BaseAccountModel.COST_OF_SALES, BaseAccountModel.OTHER_EXPENSE):
            return True
        else:
            return False


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

    def in_fiscal_year(self):
        '''
        Determines whether the :attr:`BaseJournalEntry.date` is in the
        current :class:`FiscalYear`.

        Returns True if there is no current :class:`FiscalYear`.

        :returns: Whether :attr:`date` is in the current :class:`FiscalYear`.
        :rtype: bool
        '''
        current_year_start = FiscalYear.objects.current_start()
        if current_year_start is not None and current_year_start > self.date:
            return False
        return True


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

    def get_entry_number(self):
        return self.get_journal_entry().get_number()

    def get_final_account_balance(self):
        """Returns Account balance after transaction has occured."""
        acct_balance = self.account.balance
        query = (models.Q(date__gt=self.date) |
                (models.Q(date=self.date) & models.Q(id__gt=self.id)))
        newer_transactions = self.account.transaction_set.filter(
                query).aggregate(models.Sum('balance_delta'))
        acct_balance -= newer_transactions.get('balance_delta__sum') or 0
        if self.account.flip_balance():
            acct_balance *= -1
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


class FiscalYear(CachingMixin, models.Model):
    '''
    A model for storing data about the Company's Past and Present Fiscal Years.

    The Current Fiscal Year is used for generating Account balance's and
    Archiving :class:`Account` instances into :class:`HistoricalAccount`.

    .. seealso::

        View :func:`add_fiscal_year`
            This view processes all actions required for starting a New Fiscal
            Year.

    .. attribute:: year

        The ending Year of the Financial Year.

    .. attribute:: end_month

        The ending Month of the Financial Year. Stored as integers, displayed
        with full names.

    .. attribute:: period

        The length of the Fiscal Year in months. Available choices are 12 or
        13.

    .. attribute:: date

        The first day of the last month of the Fiscal Year. This is not
        editable, it is generated by the :class:`FiscalYear` when saved, using
        the :attr:`month` and :attr:`year` values.
    '''
    PERIOD_CHOICES = (
        (12, '12 Months'),
        (13, '13 Months')
    )
    MONTH_CHOICES = tuple((num, mon) for num, mon
            in enumerate(calendar.month_name[1:], 1))
    year = models.PositiveIntegerField()
    end_month = models.PositiveSmallIntegerField(choices=MONTH_CHOICES)
    period = models.PositiveIntegerField(choices=PERIOD_CHOICES)
    date = models.DateField(editable=False, blank=True)

    objects = FiscalYearManager()

    class Meta:
        ordering = ('date',)
        get_latest_by = ('date',)

    def __unicode__(self):
        return "Fiscal Year {0}-{1}".format(self.year, self.end_month)

    def save(self, *args, **kwargs):
        '''
        The :class:`FiscalYear` ``save`` method will generate the
        :class:`~datetime.date` object for the :attr:`date` attribute.
        '''
        self.full_clean()
        self.date = datetime.date(self.year, self.end_month, 1)
        super(FiscalYear, self).save(*args, **kwargs)
