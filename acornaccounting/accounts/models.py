import calendar
import datetime
from decimal import Decimal

from caching.base import CachingManager, CachingMixin, cached_method
from django.core.urlresolvers import reverse
from django.db import models
from mptt.models import MPTTModel, TreeForeignKey, TreeManager

from entries.models import Transaction

from .managers import AccountManager


class BaseAccountModel(MPTTModel, CachingMixin):
    """Abstract class storing common attributes of Headers and Accounts.

    Subclasses must implement the ``_calculate_full_number`` and
    ``_get_change_tree`` methods.

    """
    # TODO: Move to constants.py
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
    full_number = models.CharField(max_length=7, blank=True, null=True,
                                   editable=False)

    class Meta:
        abstract = True
        ordering = ['name']

    class MPTTMeta:
        order_insertion_by = ['name']

    def flip_balance(self):
        if self.type in (self.ASSET, self.EXPENSE, self.COST_OF_SALES,
                         self.OTHER_EXPENSE):
            return True
        else:
            return False

    def clean(self):
        """Set the ``type`` and calculate the ``full_number``.

        The ``type`` attribute will be inherited from the ``parent`` and
        the ``full_number`` will be calculated if the object has an ``id``.

        """
        if self.parent:
            self.type = self.parent.type
        if self.id:
            self.full_number = self._calculate_full_number()
        return super(BaseAccountModel, self).clean()

    def delete(self, *args, **kwargs):
        """Renumber Headers or Accounts when deleted."""
        items_to_change = self._get_change_tree()
        if self in items_to_change:
            items_to_change.remove(self)
        super(BaseAccountModel, self).delete(*args, **kwargs)
        self._resave_items(items_to_change)

    def save(self, *args, **kwargs):
        """Resave Headers or Accounts if the ``parent`` has changed.

        This method first checks to see if the ``parent`` attribute has
        changed. If so, it will cause the object and all related objects(the
        ``change_tree``) to be saved once the pending changes have been saved.

        """
        tree_has_changed = (self._has_field_changed("parent") or
                            self._has_field_changed("name"))
        if tree_has_changed and self.id:
            db_copy = self.__class__.objects.get(id=self.id)
            items_to_change = db_copy._get_change_tree()
        else:
            items_to_change = []
        self.full_clean()
        super(BaseAccountModel, self).save(*args, **kwargs)
        self.__class__.objects.rebuild()
        if tree_has_changed:
            items_to_change += self._get_change_tree()
            self._resave_items(items_to_change)

    def get_full_number(self):
        """Retrieve the Full Number from the model field."""
        if self.full_number is not None:
            return self.full_number
        else:
            try:
                return self._calculate_full_number()
            except ValueError:
                return None
    get_full_number.short_description = "Number"

    def _has_field_changed(self, field):
        """Determine if this instance's field has changed."""
        if self.id:
            database_copy = self.__class__.objects.get(id=self.id)
            has_changed = getattr(database_copy, field) != getattr(self, field)
        else:
            has_changed = True
        return has_changed

    def _resave_items(self, items):
        """Save each item."""
        if self in items:
            items.remove(self)
        for item in items:
            item.save()


class Header(BaseAccountModel):
    """Groups Accounts Together."""

    parent = TreeForeignKey('self', blank=True, null=True)
    active = models.BooleanField(default=True)

    objects = TreeManager()

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('accounts.views.show_accounts_chart',
                       args=[str(self.slug)])

    def account_number(self):
        tree = self.get_root().get_descendants(include_self=True)
        number = list(tree).index(self)
        return number

    def get_account_balance(self):
        """Traverse child Headers and Accounts to generate the current balance.

        :returns: The Value Balance of all :class:`Accounts<Account>` and
                :class:`Headers<Header>` under this Header.
        :rtype: :class:`decimal.Decimal`
        """
        balance = Decimal("0.00")
        child_headers = self.get_children()
        for header in child_headers:
            balance += header.get_account_balance()
        for account in self.account_set.all():
            balance += account.get_balance()
        return balance

    def _calculate_full_number(self):
        """Use type and tree position to generate full account number"""
        if self.parent:
            full_number = "{0}-{1:02d}000".format(self.type,
                                                  self.account_number())
        else:
            full_number = "{0}-00000".format(self.type)
        return full_number

    def _get_change_tree(self):
        """Get extra :class:`Headers<Header>` and :class:`Accounts<Account>`.

        A change in a :class:`Header` may cause changes in the number of Headers
        up to it's grandfather.

        We only save one :class:`Account` under each :class:`Header` because
        each :class:`Account` will save it's siblings.

        :returns: Additional instances to save.
        :rtype: list of :class:`Headers<Header>` and :class:`Accounts<Account>`

        """
        if self.parent and self.parent.parent:
            headers_to_change = list(self.parent.parent.get_descendants())
        else:
            headers_to_change = list(Header.objects.filter(type=self.type))
        accounts_to_change = [account for header in headers_to_change for
                              account in list(header.account_set.all())[-1:]]
        return headers_to_change + accounts_to_change


class Account(BaseAccountModel):
    """Holds information on Accounts."""
    balance = models.DecimalField(help_text="The balance is the credit/debit "
                                  "balance, not the value balance.",
                                  max_digits=19, default="0.00",
                                  verbose_name="Current Balance",
                                  decimal_places=4)
    reconciled_balance = models.DecimalField(
        help_text="The Account's currently reconciled balance.",
        max_digits=19, decimal_places=4, default="0.00")

    parent = models.ForeignKey(Header)
    active = models.BooleanField(default=True)
    bank = models.BooleanField(default=False, help_text="Mark as a Bank.")
    last_reconciled = models.DateField(null=True, blank=True)

    objects = AccountManager()

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('accounts.views.show_account_detail',
                       args=[str(self.slug)])

    def account_number(self):
        siblings = self.get_siblings(include_self=True).order_by('name')
        if self in siblings:
            number = list(siblings).index(self) + 1
        else:
            siblings = list(siblings) + [self]
            number = sorted(siblings, key=lambda x: x.name).index(self) + 1
        return number

    # TODO: get_value_balance()?
    def get_balance(self):
        """
        Returns the value balance for the :class:`Account`.

        The :class:`Account` model stores the credit/debit balance in the
        :attr:`balance` field. This method will convert the credit/debit
        balance to a value balance for :attr:`Account.type` where a debit
        increases the :class:`Account's<Account>` value, instead of decreasing
        it(the normal action).

        The ``Current Year Earnings`` :class:`Account` does not source it's
        :attr:`~Account.balance` field but instead uses the Sum of all
        :class:`Accounts<Account>` with :attr:`~BaseAccountModel.type` of 4 to
        8.

        .. seealso::

            :meth:`~BaseAccountModel.flip_balance` method for more information
            on value balances.

        :returns: The Account's current value balance.
        :rtype: :class:`decimal.Decimal`
        """
        if self.name == "Current Year Earnings":
            balance = Account.objects.filter(type__in=range(4, 9)).aggregate(
                models.Sum('balance')).get('balance__sum') or Decimal(0)
        else:
            balance = self.balance
        if self.flip_balance():
            balance *= -1
        return balance

    @cached_method
    def get_balance_by_date(self, date):
        """
        Calculate the :class:`Account's<Account>` balance at the end of a
        specific ``date``.

        For the ``Current Year Earnings`` :class:`Account`,
        :class:`Transactions<Transaction>` from all :class:`Accounts<Account>`
        with :attr:`~BaseAccountModel.type` of 4 to 8 will be used.

        :param date: The day whose balance should be returned.
        :type date: datetime.date
        :returns: The Account's balance at the end of the specified date.
        :rtype: :class:`decimal.Decimal`
        """
        if self.name == "Current Year Earnings":
            transaction_set = Transaction.objects.filter(
                account__type__in=range(4, 9))
        else:
            transaction_set = self.transaction_set
        past_transactions = transaction_set.filter(date__lte=date).reverse()

        if self.name == "Current Year Earnings":
            return (past_transactions.aggregate(
                models.Sum('balance_delta'))['balance_delta__sum'] or
                Decimal(0))
        elif past_transactions:
            return past_transactions[0].get_final_account_balance()
        else:
            transaction_sum = (transaction_set.all().aggregate(
                models.Sum('balance_delta'))['balance_delta__sum'] or
                Decimal(0))
            balance = self.balance - transaction_sum
            if self.flip_balance():
                balance *= -1
            return balance

    def get_balance_change_by_month(self, date):
        """
        Calculates the :class:`Accounts<Account>` net change in balance for the
        month of the specified ``date``.

        For the ``Current Year Earnings`` :class:`Account`,
        :class:`Transactions<Transaction>` from all :class:`Accounts<Account>`
        with :attr:`~BaseAccountModel.type` of 4 to 8 will be used.

        :param date: The month to calculate the net change for.
        :type date: datetime.date
        :returns: The Account's net balance change for the specified month.
        :rtype: :class:`decimal.Decimal`
        """
        days_in_month = calendar.monthrange(date.year, date.month)[1]
        first_day = datetime.date(date.year, date.month, 1)
        last_day = datetime.date(date.year, date.month, days_in_month)
        query = models.Q(date__gte=first_day, date__lte=last_day)
        if self.name == "Current Year Earnings":
            query.add(models.Q(account__type__in=range(4, 9)), models.Q.AND)
        else:
            query.add(models.Q(account__id=self.id), models.Q.AND)
        (_, _, net_change) = Transaction.objects.filter(query).get_totals(
            net_change=True)
        if self.flip_balance():
            net_change *= -1
        return net_change

    def _calculate_full_number(self):
        """Use parent and sibling positions to generate full account number."""
        full_number = (self.parent.get_full_number()[:-3] +
                       "{0:03d}".format(self.account_number()))
        return full_number

    def _get_change_tree(self):
        """Get this instance's siblings."""
        return list(Account.objects.filter(parent=self.parent))


class HistoricalAccount(CachingMixin, models.Model):
    """
    A model for Archiving Historical Account Data.
    It stores an :class:`Account's<Account>` balance (for Assets, Liabilities
    and Equities) or net_change (for Incomes and Expenses) for a certain month
    in a previous :class:`Fiscal Years`.

    Hard data is stored in additon to a link back to the originating
    :class:`Account`.

    .. note::

        This model is automatically generated by the
        :func:`~fiscalyears.views.add_fiscal_year` view.

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

        A :class:`datetime.date` object representing the 1st day of the Month
        and Year the archive was created.

    """
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, blank=True,
                                null=True)
    number = models.CharField(max_length=7)
    name = models.CharField(max_length=50)
    type = models.PositiveSmallIntegerField(
        choices=BaseAccountModel.TYPE_CHOICES)
    amount = models.DecimalField(max_digits=19, decimal_places=4)
    date = models.DateField()

    objects = CachingManager()

    class Meta:
        ordering = ['date', 'number']
        get_latest_by = ('date', )
        unique_together = ('date', 'name')

    def __unicode__(self):
        return '{0}/{1} - {2}'.format(self.date.year, self.date.month,
                                      self.name)

    @cached_method
    def get_absolute_url(self):
        """
        The default URL for a HistoricalAccount points to the listing for the
        :attr:`date's<date>` ``month`` and ``year``.
        """
        return reverse('accounts.views.show_account_history',
                       kwargs={'month': self.date.month,
                               'year': self.date.year})

    @cached_method
    def get_amount(self):
        """
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

        """
        if self.flip_balance():
            return self.amount * -1
        else:
            return self.amount

    @cached_method
    def flip_balance(self):
        """
        Determines whether the :attr:`HistoricalAccount.amount` should be
        flipped based on the :attr:`HistoricalAccount.type`.

        For example, debits(negative :attr:`HistoricalAccount.amount`) increase
        the value of Assets, Expenses, Cost of Sales and Other Expenses, while
        decreasing the value of all other
        :attr:`Account Types<BaseAccountModel.TYPE_CHOICES>`.

        In essence, this method will return ``True`` if the credit/debit amount
        needs to be negated(multiplied by -1) to display the value amount, and
        ``False`` if the credit/debit amount is the displayable value amount.

        """
        if self.type in (BaseAccountModel.ASSET, BaseAccountModel.EXPENSE,
                         BaseAccountModel.COST_OF_SALES,
                         BaseAccountModel.OTHER_EXPENSE):
            return True
        else:
            return False
