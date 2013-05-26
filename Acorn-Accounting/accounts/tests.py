import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.db.models import ProtectedError
from django.db.utils import IntegrityError
from django.template.defaultfilters import slugify
from django.test import TestCase
from django.utils.timezone import utc

from .models import Header, Account, JournalEntry, BankReceivingEntry, \
        BankSpendingEntry, Transaction, Event, HistoricalAccount, FiscalYear
from .forms import JournalEntryForm, TransactionFormSet, TransferFormSet, \
        BankReceivingForm, BankReceivingTransactionFormSet, BankSpendingForm, \
        BankSpendingTransactionFormSet, DateRangeForm, AccountReconcileForm, \
        ReconcileTransactionFormSet, FiscalYearForm, \
        FiscalYearAccountsFormSet


def create_header(name, parent=None, cat_type=2):
    return Header.objects.create(name=name, parent=parent, type=cat_type, slug=slugify(name))


def create_account(name, parent, balance, cat_type=2, bank=False):
    return Account.objects.create(name=name, slug=slugify(name), parent=parent, balance=balance,
                                  type=cat_type, bank=bank)


def create_entry(date, memo):
    return JournalEntry.objects.create(date=date, memo=memo)


def create_transaction(entry, account, delta):
    return Transaction.objects.create(journal_entry=entry, account=account, detail=entry.memo,
                                      balance_delta=delta)


class BaseAccountModelTests(TestCase):
    def test_balance_flip(self):
        '''
        Tests that Asset, Expense, Cost of Sales, and Other Expenses
        have there balances flipped.
        (i.e., debiting these account types should _increase_ their value)
        '''
        asset_header = create_header('asset', cat_type=1)
        expense_header = create_header('expense', cat_type=6)
        cost_header = create_header('cost', cat_type=5)
        oth_expense_header = create_header('oth_expense', cat_type=8)

        asset_acc = create_account('asset', asset_header, 0, 1)
        expense_acc = create_account('expense', expense_header, 0, 6)
        cost_acc = create_account('cost', cost_header, 0, 5)
        oth_expense_acc = create_account('oth_expense', oth_expense_header, 0, 8)

        entry = create_entry(datetime.date.today(), 'Entry')
        create_transaction(entry, asset_acc, -20)
        create_transaction(entry, expense_acc, -20)
        create_transaction(entry, cost_acc, -20)
        create_transaction(entry, oth_expense_acc, -20)

        asset_header = Header.objects.get(name='asset')
        expense_header = Header.objects.get(name='expense')
        cost_header = Header.objects.get(name='cost')
        oth_expense_header = Header.objects.get(name='oth_expense')

        asset_acc = Account.objects.get(name='asset')
        expense_acc = Account.objects.get(name='expense')
        cost_acc = Account.objects.get(name='cost')
        oth_expense_acc = Account.objects.get(name='oth_expense')

        self.assertEqual(asset_acc.get_balance(), 20)
        self.assertEqual(asset_header.get_account_balance(), 20)
        self.assertEqual(expense_acc.get_balance(), 20)
        self.assertEqual(expense_header.get_account_balance(), 20)
        self.assertEqual(cost_acc.get_balance(), 20)
        self.assertEqual(cost_header.get_account_balance(), 20)
        self.assertEqual(oth_expense_acc.get_balance(), 20)
        self.assertEqual(oth_expense_header.get_account_balance(), 20)

        create_transaction(entry, asset_acc, 40)
        create_transaction(entry, expense_acc, 40)
        create_transaction(entry, cost_acc, 40)
        create_transaction(entry, oth_expense_acc, 40)

        asset_header = Header.objects.get(name='asset')
        expense_header = Header.objects.get(name='expense')
        cost_header = Header.objects.get(name='cost')
        oth_expense_header = Header.objects.get(name='oth_expense')

        asset_acc = Account.objects.get(name='asset')
        expense_acc = Account.objects.get(name='expense')
        cost_acc = Account.objects.get(name='cost')
        oth_expense_acc = Account.objects.get(name='oth_expense')

        self.assertEqual(asset_acc.get_balance(), -20)
        self.assertEqual(asset_header.get_account_balance(), -20)
        self.assertEqual(expense_acc.get_balance(), -20)
        self.assertEqual(expense_header.get_account_balance(), -20)
        self.assertEqual(cost_acc.get_balance(), -20)
        self.assertEqual(cost_header.get_account_balance(), -20)
        self.assertEqual(oth_expense_acc.get_balance(), -20)
        self.assertEqual(oth_expense_header.get_account_balance(), -20)


class HeaderModelTests(TestCase):
    def test_get_account_balance(self):
        '''
        Tests get_account_balance with only direct children of a Header.
        '''
        header = create_header('Initial')
        account = create_account('Account', header, 0)
        entry = create_entry(datetime.date.today(), 'test entry')
        create_transaction(entry, account, -20)
        self.assertEqual(header.get_account_balance(), -20)

    def test_get_account_balance_inherit(self):
        '''
        Tests that get_account_balance calculates recursively.
        '''
        top_head = create_header('Initial')
        top_acc = create_account('Account', top_head, 0)
        child_head = create_header('child', top_head)
        child_acc = create_account('child', child_head, 0)
        gchild_head = create_header('gchild', child_head)
        gchild_acc = create_account('gchild', gchild_head, 0)
        gchild_sib_head = create_header('gchild sibling', child_head)
        gchild_sib_acc = create_account('gchild sibling', gchild_sib_head, 0)
        entry = create_entry(datetime.date.today(), 'test entry')
        create_transaction(entry, top_acc, -20)
        create_transaction(entry, child_acc, -20)
        create_transaction(entry, gchild_acc, -20)
        create_transaction(entry, gchild_sib_acc, -20)
        self.assertEqual(top_head.get_account_balance(), -80)
        self.assertEqual(child_head.get_account_balance(), -60)
        self.assertEqual(gchild_head.get_account_balance(), -20)
        self.assertEqual(gchild_sib_head.get_account_balance(), -20)

    def test_presave_signal_inherit_type(self):
        '''
        Tests that child Headers inherit their root Header's type.
        '''
        top_head = create_header('Initial')
        child_head = Header.objects.create(name='Child', parent=top_head, slug='child')
        gchild_head = Header.objects.create(name='gChild', parent=child_head, slug='gchild')
        self.assertEqual(top_head.type, child_head.type)
        self.assertEqual(top_head.type, gchild_head.type)

    def test_presave_signal_rootnode_type_fail(self):
        '''
        Tests that root Headers require a type.
        '''
        head = Header(name='initial', slug='initial', type=None)
        self.assertRaisesMessage(IntegrityError, 'accounts_header.type may not be NULL', head.save)

    def test_root_node_get_number(self):
        '''
        Tests that a root Header number is it's type
        '''
        asset = Header.objects.create(name='asset', slug='asset', type=1)
        liability = Header.objects.create(name='liability', slug='liability', type=2)
        self.assertEqual(Header.objects.all()[0].get_full_number(), '{0}-0000'.format(asset.type))
        self.assertEqual(Header.objects.all()[1].get_full_number(), '{0}-0000'.format(liability.type))

    def test_child_node_get_number(self):
        '''
        Tests that child Headers are numbered by type and alphabetical tree position
        '''
        asset = Header.objects.create(name='asset', slug='asset', type=1)
        asset_child = Header.objects.create(name='I will be second alphabetically', slug='asset-child', parent=asset)
        self.assertEqual(Header.objects.get(id=asset.id).get_full_number(), '{0}-0000'.format(asset.type))
        self.assertEqual(Header.objects.get(id=asset_child.id).get_full_number(), '{0}-0100'.format(asset_child.type))
        asset_child2 = Header.objects.create(name='And I will be first alphabetically', slug='asset-child-2', parent=asset)
        self.assertEqual(Header.objects.get(id=asset_child2.id).get_full_number(), '{0}-0100'.format(asset_child2.type))
        self.assertEqual(Header.objects.get(id=asset_child.id).get_full_number(), '{0}-0200'.format(asset_child.type))
        asset_child2_child = Header.objects.create(name='I will steal spot 2 since I am a child of spot 1', slug='asset-child-2-child', parent=asset_child2)
        self.assertEqual(Header.objects.get(id=asset_child2.id).get_full_number(), '{0}-0100'.format(asset_child2.type))
        self.assertEqual(Header.objects.get(id=asset_child2_child.id).get_full_number(), '{0}-0200'.format(asset_child2.type))
        self.assertEqual(Header.objects.get(id=asset_child.id).get_full_number(), '{0}-0300'.format(asset_child.type))

        liability = create_header('I am not in the asset tree!', None)
        liability_child = create_header('me too', liability)
        self.assertEqual(Header.objects.get(id=liability.id).get_full_number(), '{0}-0000'.format(liability.type))
        self.assertEqual(Header.objects.get(id=liability_child.id).get_full_number(), '{0}-0100'.format(liability_child.type))


class AccountModelTests(TestCase):
    def setUp(self):
        self.top_head = create_header('Initial')
        self.child_head = Header.objects.create(name='Child', parent=self.top_head, slug='child')
        self.gchild_head = Header.objects.create(name='gChild', parent=self.child_head, slug='gchild')
        self.child_acc = Account.objects.create(name='child', parent=self.child_head, balance=0, slug='child')
        self.gchild_acc = Account.objects.create(name='gChild', parent=self.gchild_head, balance=0, slug='gchild')

    def test_presave_signal_inherit_type(self):
        '''
        Tests that Accounts inherit their type from their root Header.
        '''
        self.assertEqual(self.child_acc.type, self.top_head.type)
        self.assertEqual(self.gchild_acc.type, self.top_head.type)

    def test_account_get_number(self):
        '''
        Tests that Accounts are numbered according to parent number and alphabetical
        position in siblings list.
        '''
        self.assertEqual(self.child_acc.get_full_number(), '{0}-{1:02d}{2:02d}'.format(self.child_acc.type, self.child_acc.parent.account_number(),
                                                                                  self.child_acc.account_number()))
        self.assertEqual(self.gchild_acc.get_full_number(), '{0}-{1:02d}{2:02d}'.format(self.gchild_acc.type, self.gchild_acc.parent.account_number(),
                                                                                  self.gchild_acc.account_number()))

    def test_get_balance_by_date(self):
        '''
        The ``get_balance_by_date`` function should return the ``Accounts``
        balance at the end of the ``date`` if there is a ``Transaction`` on the
        ``date``.
        '''
        date = datetime.date.today()
        entry = create_entry(date, 'entry')
        create_transaction(entry, self.child_acc, 20)
        self.assertEqual(self.child_acc.get_balance_by_date(date), 20)

    def test_get_balance_by_date_flipped(self):
        '''
        The ``get_balance_by_date`` function should flip the sign of the
        returned ``balance`` if the ``Account`` is an Asset, Expense, Cost of
        Sale, or Other Expense (indicated by ``type`` 1, 6, 5 and 8,
        respectively.
        '''
        asset_header = create_header('asset', cat_type=1)
        expense_header = create_header('expense', cat_type=6)
        cost_header = create_header('cost', cat_type=5)
        oth_expense_header = create_header('oth_expense', cat_type=8)
        asset_acc = create_account('asset', asset_header, 0, 1)
        expense_acc = create_account('expense', expense_header, 0, 6)
        cost_acc = create_account('cost', cost_header, 0, 5)
        oth_expense_acc = create_account('oth_expense', oth_expense_header, 0, 8)

        today = datetime.date.today()
        entry = create_entry(today, 'Entry')
        create_transaction(entry, asset_acc, -20)
        create_transaction(entry, expense_acc, -20)
        create_transaction(entry, cost_acc, -20)
        create_transaction(entry, oth_expense_acc, -20)

        self.assertEqual(asset_acc.get_balance_by_date(today), 20)
        self.assertEqual(expense_acc.get_balance_by_date(today), 20)
        self.assertEqual(cost_acc.get_balance_by_date(today), 20)
        self.assertEqual(oth_expense_acc.get_balance_by_date(today), 20)

    def test_get_balance_by_date_previous_transactions(self):
        '''
        The ``get_balance_by_date`` function should return the ``Accounts``
        balance at the end of the ``date`` if there are ``Transactions`` on
        previous days but not on the input ``date``.
        '''
        date = datetime.date.today() - datetime.timedelta(days=1)
        entry = create_entry(date, 'entry')
        create_transaction(entry, self.child_acc, 20)
        create_transaction(entry, self.child_acc, 20)
        self.assertEqual(self.child_acc.get_balance_by_date(datetime.date.today()), 40)

    def test_get_balance_by_date_future_transactions(self):
        '''
        The ``get_balance_by_date`` method should return a Decimal value of 0
        if the ``Account`` has ``Transactions`` only after the ``date``.
        '''
        date = datetime.date.today() + datetime.timedelta(days=1)
        entry = create_entry(date, 'entry')
        create_transaction(entry, self.child_acc, 20)
        create_transaction(entry, self.child_acc, 20)
        self.assertEqual(self.child_acc.get_balance_by_date(datetime.date.today()), 0)

    def test_get_balance_by_date_no_transactions(self):
        '''
        The ``get_balance_by_date`` method should return a Decimal value of 0
        if the ``Account`` has no ``Transactions``.
        '''
        date = datetime.date.today()
        balance = self.child_acc.get_balance_by_date(date=date)
        self.assertTrue(isinstance(balance, Decimal))
        self.assertEqual(balance, 0)

    def test_get_balance_by_date_multiple_transactions(self):
        '''
        The ``get_balance_by_date`` function should return the ``Accounts``
        balance at the end of the ``date`` if there are multiple
        ``Transactions`` on the ``date``.
        '''
        date = datetime.date.today()
        entry = create_entry(date, 'entry')
        create_transaction(entry, self.child_acc, 20)
        create_transaction(entry, self.child_acc, 20)
        self.assertEqual(self.child_acc.get_balance_by_date(date), 40)

    def test_get_balance_by_date_previous_and_current_transactions(self):
        '''
        The ``get_balance_by_date`` function should return the ``Accounts``
        balance at the end of the ``date`` if there are ``Transactions`` on
        previous days and on the input ``date``.
        '''
        past_date = datetime.date.today() - datetime.timedelta(days=1)
        entry = create_entry(past_date, 'older entry')
        create_transaction(entry, self.child_acc, 20)
        create_transaction(entry, self.child_acc, 20)
        today = datetime.date.today()
        entry = create_entry(today, 'today entry')
        create_transaction(entry, self.child_acc, 20)
        create_transaction(entry, self.child_acc, 20)
        self.assertEqual(self.child_acc.get_balance_by_date(today), 80)

    def test_get_balance_by_date_future_and_current_transactions(self):
        '''
        The ``get_balance_by_date`` function should return the ``Accounts``
        balance at the end of the ``date`` if there are ``Transactions`` on
        future days and on the input ``date``.
        '''
        future_date = datetime.date.today() + datetime.timedelta(days=1)
        entry = create_entry(future_date, 'newer entry')
        create_transaction(entry, self.child_acc, 20)
        create_transaction(entry, self.child_acc, 20)
        today = datetime.date.today()
        entry = create_entry(today, 'today entry')
        create_transaction(entry, self.child_acc, 20)
        create_transaction(entry, self.child_acc, 20)
        self.assertEqual(self.child_acc.get_balance_by_date(today), 40)

    def test_get_balance_by_date_previous_and_future_transactions(self):
        '''
        The ``get_balance_by_date`` function should return the ``Accounts``
        balance at the end of the ``date`` if there are ``Transactions`` on
        previous days and after the input ``date``, but not on it.
        '''
        past_date = datetime.date.today() - datetime.timedelta(days=1)
        entry = create_entry(past_date, 'older entry')
        create_transaction(entry, self.child_acc, 20)
        create_transaction(entry, self.child_acc, 20)
        future = datetime.date.today() + datetime.timedelta(days=1)
        entry = create_entry(future, 'future entry')
        create_transaction(entry, self.child_acc, 20)
        create_transaction(entry, self.child_acc, 20)
        self.assertEqual(self.child_acc.get_balance_by_date(datetime.date.today()), 40)

    def test_get_balance_by_date_prev_curr_and_future_transactions(self):
        '''
        The ``get_balance_by_date`` function should return the ``Accounts``
        balance at the end of the ``date`` if there are ``Transactions`` on
        previous and future days and on the input ``date``.
        '''
        past_date = datetime.date.today() - datetime.timedelta(days=1)
        entry = create_entry(past_date, 'older entry')
        create_transaction(entry, self.child_acc, 20)
        create_transaction(entry, self.child_acc, 20)
        today = datetime.date.today()
        entry = create_entry(today, 'today entry')
        create_transaction(entry, self.child_acc, 20)
        create_transaction(entry, self.child_acc, 20)
        future_date = datetime.date.today() + datetime.timedelta(days=1)
        entry = create_entry(future_date, 'newer entry')
        create_transaction(entry, self.child_acc, 20)
        create_transaction(entry, self.child_acc, 20)
        self.assertEqual(self.child_acc.get_balance_by_date(today), 80)

    def test_get_balance_change_by_month(self):
        '''
        The ``get_balance_change_by_month`` method should return the
        ``Accounts`` net change for the designated ``month`` if there is a
        ``Transaction`` in the ``month``.
        '''
        today = datetime.date.today()
        entry = create_entry(today, 'today entry')
        create_transaction(entry, self.child_acc, 20)
        self.assertEqual(self.child_acc.get_balance_change_by_month(today), 20)

    def test_get_balance_change_by_month_flipped(self):
        '''
        The ``get_balance_change_by_month`` method should a flipped
        net_change for ``Accounts`` that are Assets, Expenses, Cost of Sales
        or Other Expenses (``type`` 1, 6, 5, 8 respectively).
        '''
        asset_header = create_header('asset', cat_type=1)
        expense_header = create_header('expense', cat_type=6)
        cost_header = create_header('cost', cat_type=5)
        oth_expense_header = create_header('oth_expense', cat_type=8)
        asset_acc = create_account('asset', asset_header, 0, 1)
        expense_acc = create_account('expense', expense_header, 0, 6)
        cost_acc = create_account('cost', cost_header, 0, 5)
        oth_expense_acc = create_account('oth_expense', oth_expense_header, 0, 8)

        today = datetime.date.today()
        entry = create_entry(today, 'Entry')
        create_transaction(entry, asset_acc, -20)
        create_transaction(entry, expense_acc, -20)
        create_transaction(entry, cost_acc, -20)
        create_transaction(entry, oth_expense_acc, -20)

        self.assertEqual(asset_acc.get_balance_change_by_month(today), 20)
        self.assertEqual(expense_acc.get_balance_change_by_month(today), 20)
        self.assertEqual(cost_acc.get_balance_change_by_month(today), 20)
        self.assertEqual(oth_expense_acc.get_balance_change_by_month(today), 20)

    def test_get_balance_change_by_month_multiple_transactions(self):
        '''
        The ``get_balance_change_by_month`` method should return the
        ``Accounts`` net balance change for the desingated ``month`` if there
        are multiple ``Transactions`` in the ``month``.
        '''
        today = datetime.date.today()
        entry = create_entry(today, 'today entry')
        create_transaction(entry, self.child_acc, 20)
        create_transaction(entry, self.child_acc, 20)
        self.assertEqual(self.child_acc.get_balance_change_by_month(today), 40)

    def test_get_balance_change_by_month_previous_transactions(self):
        '''
        The ``get_balance_change_by_month`` method should return a ``Decimal``
        with a value of ``0`` if there are ``Transactions`` in previous months
        but not in the ``date`` input.
        '''
        today = datetime.date.today()
        months_ago = today - datetime.timedelta(days=60)
        entry = create_entry(months_ago, 'past entry')
        create_transaction(entry, self.child_acc, 20)
        create_transaction(entry, self.child_acc, 20)
        self.assertEqual(self.child_acc.get_balance_change_by_month(today), 0)

    def test_get_balance_change_by_month_prev_and_curr_transactions(self):
        '''
        The ``get_balance_change_by_month`` method should return the
        ``Accounts`` correct net balance change for the desingated ``month``
        if there are multiple ``Transactions`` in the ``month`` and in months
        before.
        '''
        today = datetime.date.today()
        months_ago = today - datetime.timedelta(days=60)
        entry = create_entry(months_ago, 'past entry')
        create_transaction(entry, self.child_acc, 20)
        create_transaction(entry, self.child_acc, 20)
        entry = create_entry(today, 'today entry')
        create_transaction(entry, self.child_acc, 20)
        create_transaction(entry, self.child_acc, 20)
        self.assertEqual(self.child_acc.get_balance_change_by_month(today), 40)

    def test_get_balance_change_by_month_future_transactions(self):
        '''
        The ``get_balance_change_by_month`` method should return a ``Decimal``
        with a value of ``0`` if there are ``Transactions`` in future months
        but not in the ``date`` input.
        '''
        today = datetime.date.today()
        future_month = today + datetime.timedelta(days=60)
        entry = create_entry(future_month, 'future entry')
        create_transaction(entry, self.child_acc, 20)
        create_transaction(entry, self.child_acc, 20)
        self.assertEqual(self.child_acc.get_balance_change_by_month(today), 0)

    def test_get_balance_change_by_month_future_and_curr_transactions(self):
        '''
        The ``get_balance_change_by_month`` method should return the
        ``Accounts`` correct net balance change for the desingated ``month``
        if there are multiple ``Transactions`` in the ``month`` and in future
        months.
        '''
        today = datetime.date.today()
        future_month = today + datetime.timedelta(days=60)
        entry = create_entry(future_month, 'future entry')
        create_transaction(entry, self.child_acc, 20)
        create_transaction(entry, self.child_acc, 20)
        entry = create_entry(today, 'today entry')
        create_transaction(entry, self.child_acc, 20)
        create_transaction(entry, self.child_acc, 20)
        self.assertEqual(self.child_acc.get_balance_change_by_month(today), 40)

    def test_get_balance_change_by_month_prev_futu_and_curr_transactions(self):
        '''
        The ``get_balance_change_by_month`` method should return the
        ``Accounts`` correct net balance change for the desingated ``month``
        if there are multiple ``Transactions`` in the ``month`` and in future
        and past months.
        '''
        today = datetime.date.today()
        future_month = today + datetime.timedelta(days=60)
        entry = create_entry(future_month, 'future entry')
        create_transaction(entry, self.child_acc, 20)
        create_transaction(entry, self.child_acc, 20)
        entry = create_entry(today, 'today entry')
        create_transaction(entry, self.child_acc, 20)
        create_transaction(entry, self.child_acc, 20)
        months_ago = today - datetime.timedelta(days=60)
        entry = create_entry(months_ago, 'past entry')
        create_transaction(entry, self.child_acc, 20)
        create_transaction(entry, self.child_acc, 20)
        self.assertEqual(self.child_acc.get_balance_change_by_month(today), 40)

    def test_get_balance_change_by_month_no_transactions(self):
        '''
        The ``get_balance_change_by_month`` method should return a ``Decimal``
        with a value of ``0`` if the account has no ``Transactions``.
        '''
        date = datetime.date.today()
        net_change = self.child_acc.get_balance_change_by_month(date=date)
        self.assertTrue(isinstance(net_change, Decimal))
        self.assertEqual(net_change, 0)

    def test_account_delete_no_transactions(self):
        '''
        Accounts can be deleted if they have no Transactions.
        '''
        self.assertEqual(Account.objects.count(), 2)
        self.child_acc.delete()
        self.assertEqual(Account.objects.count(), 1)

    def test_account_delete_with_transactions(self):
        '''
        Accounts can not be deleted if they have Transactions.
        '''
        entry = create_entry(datetime.date.today(), 'blocking entry')
        create_transaction(entry, self.child_acc, 20)
        self.assertEqual(Account.objects.count(), 2)
        self.assertRaises(ProtectedError, self.child_acc.delete)


class HistoricalAccountModelTests(TestCase):
    '''Tests the custom methods on the ``HistoricalAccount`` model.'''
    def setUp(self):
        today = datetime.date.today()
        self.liability_historical = HistoricalAccount.objects.create(
             number='2-1001', name='Test Liability', type=2, amount=Decimal('-900.25'),
             date=datetime.date(day=1, month=today.month, year=(today.year - 1)))
        self.asset_historical = HistoricalAccount.objects.create(
             number='1-1001', name='Test Asset', type=1, amount=Decimal('-9000.01'),
             date=datetime.date(day=1, month=today.month, year=(today.year - 1)))

    def test_get_amount(self):
        '''
        The ``get_amount`` function will return a flipped balance for
        ``HistoricalAccounts`` that are Assets, Cost of Sales, Expenses or
        Other Expenses (types 1, 5, 6, 8).

        A ``HistoricalAccounts`` ``amount`` is negative if it holds a debit
        balance and positive if it holds a credit balance. For types 1, 5, 6
        and 8, a debit balance is considered a positive value, and a credit
        balance has a negative value.  This function will flip the credit/debit
        balance into the value balance for these Account types.

        ``HistoricalAccounts`` will other types will return the same value as
        their ``amount``.
        '''
        self.assertEqual(self.liability_historical.get_amount(),
                Decimal('-900.25'))
        self.assertEqual(self.asset_historical.get_amount(),
                Decimal('9000.01'))

    def test_flip_balance(self):
        '''
        HistoricalAccounts that are Assets, Expenses, Cost of Sales or Other
        Expense types store their credit/debit balance in the `amount` field
        while their value balance is actually the opposite of the credit/debit
        balance, i.e. debits(a negative `amounts`) have positive values and
        credits(a positive `amount`) have negative values.

        The `flip_balance` method of the HistoricalAccount class will return
        True if the HistoricalAccount has an above type, indicating it's amount
        needs to be flipped to represent the value, and False otherwise,
        indicating the amount does not need to be flipped to represent the
        value.
        '''
        today = datetime.date.today()
        equity_historical = HistoricalAccount.objects.create(
                number='3-1001', name='Test Equity', type=3,
                amount=Decimal('4'), date=today)
        income_historical = HistoricalAccount.objects.create(
                number='4-1001', name='Test Income', type=4,
                amount=Decimal('2'), date=today)
        cost_sale_historical = HistoricalAccount.objects.create(
                number='5-1001', name='Test CoS', type=5,
                amount=Decimal('0'), date=today)
        expense_historical = HistoricalAccount.objects.create(
                number='6-1001', name='Test Expense', type=6,
                amount=Decimal('4'), date=today)
        other_income_historical = HistoricalAccount.objects.create(
                number='7-1001', name='Test Oth Income', type=7,
                amount=Decimal('2'), date=today)
        other_expense_historical = HistoricalAccount.objects.create(
                number='8-1001', name='Test Oth Expense', type=8,
                amount=Decimal('0'), date=today)
        self.assertTrue(self.asset_historical.flip_balance())
        self.assertTrue(cost_sale_historical.flip_balance())
        self.assertTrue(expense_historical.flip_balance())
        self.assertTrue(other_expense_historical.flip_balance())
        self.assertFalse(self.liability_historical.flip_balance())
        self.assertFalse(income_historical.flip_balance())
        self.assertFalse(equity_historical.flip_balance())
        self.assertFalse(other_income_historical.flip_balance())


class JournalEntryModelTests(TestCase):
    '''Tests custom methods on the BaseJournalEntry model.'''
    def test_in_fiscal_year_no_fiscal_year(self):
        '''
        If there is no current Fiscal Year, the `in_fiscal_year` method will
        return `True`.
        '''
        entry = JournalEntry.objects.create(date=datetime.date.today(),
                memo='no fiscal year')
        self.assertTrue(entry.in_fiscal_year())

    def test_in_fiscal_year_before_start(self):
        '''
        If there is a Fiscal Year, the `in_fiscal_year` method will return
        `False` if the Entry's date is before the FiscalYear's start.
        '''
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        entry_date = datetime.date(2011, 2, 5)
        entry = JournalEntry.objects.create(date=entry_date,
                memo='before fiscal year')
        self.assertEqual(FiscalYear.objects.current_start(),
                datetime.date(2012, 1, 1))
        self.assertFalse(entry.in_fiscal_year())

    def test_in_fiscal_year_after_start(self):
        '''
        If there is a Fiscal Year, the `in_fiscal_year` method will return
        `False` if the Entry's date is before the FiscalYear's start.
        '''
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        entry_date = datetime.date(2012, 2, 5)
        entry = JournalEntry.objects.create(date=entry_date,
                memo='in fiscal year')
        self.assertEqual(FiscalYear.objects.current_start(),
                datetime.date(2012, 1, 1))
        self.assertTrue(entry.in_fiscal_year())


class BankSpendingEntryModelTests(TestCase):
    def setUp(self):
        self.header = create_header('Initial')
        self.account = create_account('Account', self.header, 0)

    def test_ach_or_check_number_required(self):
        '''
        Tests that BankSpendingEntry Models requires either an ACH payment or
        check_number
        refs #97
        '''
        main_transaction = Transaction.objects.create(account=self.account, balance_delta=25)
        entry = BankSpendingEntry(check_number=None, ach_payment=None, memo='no check or ach',
                                  main_transaction=main_transaction, date=datetime.date.today())
        self.assertRaises(ValidationError, entry.save)

    def test_ach_xor_check_number(self):
        '''
        Tests that BankSpendingEntry Models requires either an ACH payment OR
        check_number exclusively
        refs #97
        '''
        main_transaction = Transaction.objects.create(account=self.account, balance_delta=25)
        entry = BankSpendingEntry(check_number="23", ach_payment=True, memo='check AND ach',
                                  main_transaction=main_transaction, date=datetime.date.today())
        self.assertRaises(ValidationError, entry.save)

    def test_save_set_transaction_date(self):
        '''
        Saving a BankSpendingEntry should set the ``date`` fields of it's
        ``main_transaction`` and the ``Transactions`` in it's
        ``transaction_set``.
        '''
        date = datetime.date.today() - datetime.timedelta(days=42)
        main_transaction = Transaction.objects.create(account=self.account, balance_delta=25)
        entry = BankSpendingEntry.objects.create(check_number="23", memo='change date',
                                  main_transaction=main_transaction, date=datetime.date.today())
        tran = Transaction.objects.create(bankspend_entry=entry, account=self.account, balance_delta=15)
        main_transaction = Transaction.objects.get(id=main_transaction.id)
        tran = Transaction.objects.get(id=tran.id)
        self.assertEqual(tran.date, datetime.date.today())
        self.assertEqual(main_transaction.date, datetime.date.today())
        entry.date = date
        entry.save()
        main_transaction = Transaction.objects.get(id=main_transaction.id)
        tran = Transaction.objects.get(id=tran.id)
        self.assertEqual(main_transaction.date, date)
        self.assertEqual(tran.date, date)

    def test_unique_check_number_per_account(self):
        '''
        A BankSpendingEntry's `check_number` should not be unique globally, but
        per Account by the `main_transaction` attribute.
        '''
        second_account = create_account('Account 2', self.header, 0)
        main_transaction1 = Transaction.objects.create(account=self.account,
                balance_delta=25)
        BankSpendingEntry.objects.create(check_number=1, ach_payment=False,
                memo='check 1 account 1', main_transaction=main_transaction1,
                date=datetime.date.today())
        main_transaction2 = Transaction.objects.create(account=second_account,
                balance_delta=25)
        BankSpendingEntry.objects.create(check_number=1, ach_payment=False,
                memo='check 1 account 2', main_transaction=main_transaction2,
                date=datetime.date.today())

        self.assertEqual(BankSpendingEntry.objects.count(), 2)

    def test_unique_check_number_per_account_fail(self):
        '''
        A BankSpendingEntry's `check_number` should not be unique globally, but
        per Account by the `main_transaction` attribute.
        A BankSpendingEntry with the same `check_number` as another
        BankSpendingEntry whose main_transactions have the same Account, is
        invalid.
        '''
        main_transaction1 = Transaction.objects.create(account=self.account,
                balance_delta=25)
        BankSpendingEntry.objects.create(check_number=1, ach_payment=False,
                memo='check 1 account 1', main_transaction=main_transaction1,
                date=datetime.date.today())
        main_transaction2 = Transaction.objects.create(account=self.account,
                balance_delta=25)
        second_entry = BankSpendingEntry(check_number=1, ach_payment=False,
                memo='check 1 account 2', main_transaction=main_transaction2,
                date=datetime.date.today())

        self.assertRaises(ValidationError, second_entry.save)


class BankReceivingEntryModelTests(TestCase):
    '''Test the custom BankSpendingEntry model methods'''
    def setUp(self):
        self.header = create_header('Initial')
        self.account = create_account('Account', self.header, 0)

    def test_save_set_transaction_date(self):
        '''
        Saving a BankReceivingEntry should set the ``date`` fields of it's
        ``main_transaction`` and the ``Transactions`` in it's
        ``transaction_set``.
        '''
        date = datetime.date.today() - datetime.timedelta(days=42)
        main_transaction = Transaction.objects.create(account=self.account, balance_delta=25)
        entry = BankReceivingEntry.objects.create(payor='test payor', memo='change date',
                                  main_transaction=main_transaction, date=datetime.date.today())
        tran = Transaction.objects.create(bankreceive_entry=entry, account=self.account, balance_delta=15)
        main_transaction = Transaction.objects.get(id=main_transaction.id)
        tran = Transaction.objects.get(id=tran.id)
        self.assertEqual(tran.date, datetime.date.today())
        self.assertEqual(main_transaction.date, datetime.date.today())
        entry = BankReceivingEntry.objects.all()[0]
        entry.date = date
        entry.save()
        main_transaction = Transaction.objects.get(id=main_transaction.id)
        tran = Transaction.objects.get(id=tran.id)
        self.assertEqual(main_transaction.date, date)
        self.assertEqual(tran.date, date)


class TransactionModelTests(TestCase):
    def test_creation(self):
        '''
        Tests that created Transactions affect Account balances.
        '''
        header = create_header('Initial')
        debited = create_account('Debited Account', header, 0)
        credited = create_account('Credited Account', header, 0)
        entry = create_entry(datetime.date.today(), 'Entry')
        create_transaction(entry=entry, account=debited, delta=-20)
        create_transaction(entry=entry, account=credited, delta=20)
        debited = Account.objects.get(name='Debited Account')
        credited = Account.objects.get(name='Credited Account')
        self.assertEqual(debited.balance, -20)
        self.assertEqual(credited.balance, 20)

    def test_account_change(self):
        '''
        Tests that balance_delta is refunded when Account changes.
        '''
        header = create_header('Account Change')
        source = create_account('Source', header, 0)
        target = create_account('Target', header, 0)
        entry = create_entry(datetime.date.today(), 'Entry')
        create_transaction(entry=entry, account=source, delta=-20)
        trans = Transaction.objects.all()[0]
        trans.account = target
        trans.save()
        source = Account.objects.get(name='Source')
        target = Account.objects.get(name='Target')
        self.assertEqual(target.balance, -20)
        self.assertEqual(source.balance, 0)

    def test_balance_change(self):
        '''
        Tests that balance change first refunds instead of being cumulative
        '''
        header = create_header('Account Change')
        source = create_account('Source', header, 0)
        entry = create_entry(datetime.date.today(), 'Entry')
        create_transaction(entry=entry, account=source, delta=-20)
        trans = Transaction.objects.all()[0]
        trans.balance_delta = 20
        trans.save()
        source = Account.objects.get(name='Source')
        self.assertEqual(source.balance, 20)

    def test_account_and_balance_change(self):
        '''
        Tests that balance_delta is refunded to source account and new
        balance_delta is applied to target account
        '''
        header = create_header('Account Change')
        source = create_account('Source', header, 0)
        target = create_account('Target', header, 0)
        entry = create_entry(datetime.date.today(), 'Entry')
        trans = create_transaction(entry=entry, account=source, delta=-20)
        trans.account = target
        trans.balance_delta = 20
        trans.save()
        source = Account.objects.get(name='Source')
        target = Account.objects.get(name='Target')
        self.assertEqual(target.balance, 20)
        self.assertEqual(source.balance, 0)

    def test_delete(self):
        '''
        Test that Transactions refund Accounts on deletion
        '''
        header = create_header('Initial')
        source = create_account('Source', header, 0)
        entry = create_entry(datetime.date.today(), 'Entry')
        trans = create_transaction(entry=entry, account=source, delta=-20)
        trans.delete()
        source = Account.objects.all()[0]
        self.assertEqual(source.get_balance(), 0)

    def test_one_transaction_account_balance(self):
        '''
        Tests get_final_account_balance for a single transaction
        '''
        header = create_header('Initial')
        source = create_account('Source', header, 0)
        entry = create_entry(datetime.date.today(), 'Entry')
        create_transaction(entry=entry, account=source, delta=-20)
        trans = Transaction.objects.all()[0]
        self.assertEqual(trans.get_final_account_balance(), -20)

    def test_two_transactions_account_balance(self):
        '''
        Tests get_final_account_balance for transactions in the same entry
        '''
        header = create_header('Initial')
        source = create_account('Source', header, 0)
        entry = create_entry(datetime.date.today(), 'Entry')
        create_transaction(entry=entry, account=source, delta=-20)
        create_transaction(entry=entry, account=source, delta=-20)
        trans_low_id = Transaction.objects.all()[0]
        trans_high_id = Transaction.objects.all()[1]
        self.assertEqual(trans_low_id.get_final_account_balance(), -20)
        self.assertEqual(trans_high_id.get_final_account_balance(), -40)

    def test_two_transactions_same_date_account_balance(self):
        '''
        Tests get_final_account_balance for transactions with different entries
        but same dates
        '''
        header = create_header('Initial')
        source = create_account('Source', header, 0)
        entry = create_entry(datetime.date.today(), 'Entry')
        entry2 = create_entry(datetime.date.today(), 'Entry2')
        create_transaction(entry=entry, account=source, delta=-20)
        create_transaction(entry=entry2, account=source, delta=-20)
        trans_low_id = Transaction.objects.all()[0]
        trans_high_id = Transaction.objects.all()[1]
        self.assertEqual(trans_low_id.get_final_account_balance(), -20)
        self.assertEqual(trans_high_id.get_final_account_balance(), -40)

    def test_two_transactions_old_second_account_balance(self):
        '''
        Tests get_final_account_balance for older transactions with higher ids
        '''
        header = create_header('Initial')
        source = create_account('Source', header, 0)
        entry = create_entry(datetime.date.today(), 'Entry')
        entry2 = create_entry(datetime.date.today() - datetime.timedelta(days=2), 'Entry2')
        create_transaction(entry=entry, account=source, delta=-20)
        create_transaction(entry=entry2, account=source, delta=-20)
        trans_newer = Transaction.objects.all()[1]
        trans_older = Transaction.objects.all()[0]
        self.assertEqual(trans_older.get_final_account_balance(), -20)
        self.assertEqual(trans_newer.get_final_account_balance(), -40)

    def test_two_transactions_old_first_account_balance(self):
        '''
        Tests get_final_account_balance for older transactions with lower ids
        '''
        header = create_header('Initial')
        source = create_account('Source', header, 0)
        entry = create_entry(datetime.date.today(), 'Entry')
        entry2 = create_entry(datetime.date.today() - datetime.timedelta(days=2), 'Entry2')
        create_transaction(entry=entry2, account=source, delta=-20)
        create_transaction(entry=entry, account=source, delta=-20)
        trans_older = Transaction.objects.all()[0]
        trans_newer = Transaction.objects.all()[1]
        self.assertEqual(trans_older.get_final_account_balance(), -20)
        self.assertEqual(trans_newer.get_final_account_balance(), -40)

    def test_transaction_get_journal_entry(self):
        '''
        Tests that get_journal_entry retrieves the correct JournalEntry
        '''
        header = create_header('Initial')
        bank_account = create_account('Bank Account', header, 0, cat_type=1, bank=True)
        account = create_account('Account', header, 0)

        journal_entry = create_entry(datetime.date.today(), 'test entry')
        je_tran = create_transaction(journal_entry, account, 25)
        self.assertEqual(je_tran.get_journal_entry(), journal_entry)

        bankspend_main = Transaction.objects.create(account=bank_account, balance_delta=50)
        bankspend = BankSpendingEntry.objects.create(date=datetime.date.today(), memo='test bankspend',
                                                     main_transaction=bankspend_main, ach_payment=True)
        bankspend_tran = Transaction.objects.create(bankspend_entry=bankspend, account=account, balance_delta=-50)
        self.assertEqual(bankspend_main.get_journal_entry(), bankspend)
        self.assertEqual(bankspend_tran.get_journal_entry(), bankspend)

        bankreceive_main = Transaction.objects.create(account=bank_account, balance_delta=-50)
        bankreceive = BankSpendingEntry.objects.create(date=datetime.date.today(), memo='test bank receive',
                                                     main_transaction=bankreceive_main, ach_payment=True)
        bankreceive_tran = Transaction.objects.create(bankspend_entry=bankreceive, account=account, balance_delta=50)
        self.assertEqual(bankreceive_main.get_journal_entry(), bankreceive)
        self.assertEqual(bankreceive_tran.get_journal_entry(), bankreceive)

    def test_transaction_save_date(self):
        '''
        Saving a Transaction should cause the Transaction to use the ``date``
        value of it's ``journal_entry``.
        '''
        date = datetime.date.today() - datetime.timedelta(days=42)
        header = create_header('Account Change')
        source = create_account('Source', header, 0)
        entry = create_entry(date, 'test entry')
        trans = create_transaction(entry, source, 20)
        self.assertEqual(trans.date, date)

    def test_transaction_save_date_no_pull(self):
        '''
        Saving a Transaction with a ``pull_date`` of ``False`` will cause the
        Transaction to not use it's ``journal_entry`` ``date`` to populate it's
        ``date`` field.
        '''
        date = datetime.date.today() - datetime.timedelta(days=42)
        header = create_header('Account Change')
        source = create_account('Source', header, 0)
        entry = create_entry(date, 'test entry')
        trans = Transaction(journal_entry=entry, account=source, balance_delta=20)
        trans.save(pull_date=False)
        self.assertEqual(trans.date, None)
        trans.date = datetime.date.today()
        trans.save(pull_date=False)
        self.assertEqual(trans.date, datetime.date.today())
        trans.save(pull_date=True)
        self.assertEqual(trans.date, date)


class FiscalYearManagerTests(TestCase):
    '''Test the manager class for FiscalYears'''
    def test_current_start_no_years(self):
        '''
        The ``current_start`` method should return ``None`` if there are no
        ``FiscalYears``.
        '''
        self.assertEqual(FiscalYear.objects.current_start(), None)

    def test_current_start_one_year(self):
        '''
        If there is only one ``FiscalYear`` the ``current_start`` method should
        return a date that is ``period`` amount of months before the
        ``end_month`` and ``year`` of the ``FiscalYear``.
        '''
        FiscalYear.objects.create(year=2012, end_month=2, period=12)
        start = datetime.date(2011, 3, 1)
        self.assertEqual(FiscalYear.objects.current_start(), start)

    def test_current_start_two_years(self):
        '''
        If there are multiple  ``FiscalYears`` the ``current_start`` method
        should return a date that is one day after the ``end_month`` and
        ``year`` of the Second to Latest ``FiscalYear``.
        '''
        FiscalYear.objects.create(year=2012, end_month=2, period=12)
        FiscalYear.objects.create(year=2012, end_month=6, period=12)
        start = datetime.date(2012, 3, 1)
        self.assertEqual(FiscalYear.objects.current_start(), start)


class FiscalYearFormTests(TestCase):
    '''
    Test the Fiscal Year creation form validation.
    '''
    def setUp(self):
        '''
        The FiscalYearForm requires a Current Year Earnings and Retained
        Earnings Equity Account if there are previous FiscalYears.
        '''
        self.equity_header = create_header('Equity', cat_type=3)
        self.retained_account = create_account('Retained Earnings', self.equity_header, 0, 3)
        self.current_earnings = create_account('Current Year Earnings', self.equity_header, 0, 3)

    def test_first_fiscal_year_creation(self):
        '''
        The first Fiscal Year created can be any month, year and period and
        does not require ``Current Year Earnings`` and ``Retained Earnings``
        Equity ``Accounts``.
        '''
        Account.objects.all().delete()
        form_data = {
                'year': 1,
                'end_month': 4,
                'period': 12
        }
        form = FiscalYearForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_valid_next_year_same_month(self):
        '''
        A valid Fiscal Year has a ``year`` greater than or equal to the current
        FiscalYear's and a ``month`` equal to the ``period``.
        '''
        FiscalYear.objects.create(year=2012, end_month=2, period=12)
        form_data = {
                'year': 2013,
                'end_month': 2,
                'period': 12
        }
        form = FiscalYearForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_valid_next_year_same_month_13(self):
        '''
        A valid Fiscal Year has a ``year`` greater than or equal to the current
        FiscalYear's and a ``month`` equal to the ``period``.
        '''
        FiscalYear.objects.create(year=2012, end_month=2, period=13)
        form_data = {
                'year': 2013,
                'end_month': 3,
                'period': 13
        }
        form = FiscalYearForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_valid_next_year_prev_month(self):
        '''
        A valid Fiscal Year has a ``year`` greater than or equal to the current
        FiscalYear's and a ``month`` less than the ``period``.
        '''
        FiscalYear.objects.create(year=2012, end_month=2, period=12)
        form_data = {
                'year': 2013,
                'end_month': 1,
                'period': 12
        }
        form = FiscalYearForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_valid_next_year_next_month_fail(self):
        '''
        A Fiscal Year is invalid if the new ``end_month`` is more than
        ``period`` months from the last ``end_month``.
        '''
        FiscalYear.objects.create(year=2012, end_month=2, period=12)
        form_data = {
                'year': 2013,
                'end_month': 3,
                'period': 12
        }
        form = FiscalYearForm(data=form_data)
        self.assertFalse(form.is_valid())

        (form_data['end_month'], form_data['period']) = (4, 13)
        form = FiscalYearForm(data=form_data)
        self.assertFalse(form.is_valid())

    def test_valid_many_years_same_month_fail(self):
        '''
        A Fiscal Year is invalid if the new ``year`` and ``end_month`` is more
        than ``period`` months from the last ``end_month``.

        Tests for bug where end_months close to previous end_month would be
        valid even if the year caused the new end date to be beyond the new
        period.
        '''
        FiscalYear.objects.create(year=2012, end_month=2, period=12)
        form_data = {
                'year': 2014,
                'end_month': 2,
                'period': 12
        }
        form = FiscalYearForm(data=form_data)
        self.assertFalse(form.is_valid())

        (form_data['end_month'], form_data['period']) = (4, 13)
        form = FiscalYearForm(data=form_data)
        self.assertFalse(form.is_valid())

    def test_valid_same_year(self):
        '''
        A valid Fiscal Year can have the same ``year`` as the current
        FiscalYear if the ``month`` is greater.
        '''
        FiscalYear.objects.create(year=2012, end_month=2, period=12)
        form_data = {
                'year': 2012,
                'end_month': 3,
                'period': 12
        }
        form = FiscalYearForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_valid_same_year_and_month_fail(self):
        '''
        A form is invalid if the ``year`` and ``month`` of the new FiscalYear
        are the same as the last's.
        '''
        FiscalYear.objects.create(year=2012, end_month=2, period=12)
        form_data = {
                'year': 2012,
                'end_month': 2,
                'period': 12
        }
        form = FiscalYearForm(data=form_data)
        self.assertFalse(form.is_valid())

    def test_valid_same_year_prev_month_fail(self):
        '''
        A form is invalid if the ``year`` of the new FiscalYear
        is the same as the last's and the ``month`` is before the last's.
        '''
        FiscalYear.objects.create(year=2012, end_month=2, period=12)
        form_data = {
                'year': 2012,
                'end_month': 1,
                'period': 12
        }
        form = FiscalYearForm(data=form_data)
        self.assertFalse(form.is_valid())

    def test_valid_prev_year_fail(self):
        '''
        Any ```FiscalYear`` with a ``year`` less than the last Year's is
        invalid.
        '''
        FiscalYear.objects.create(year=2012, end_month=2, period=12)
        form_data = {
                'year': 2011,
                'end_month': 2,
                'period': 12
        }
        form = FiscalYearForm(data=form_data)
        self.assertFalse(form.is_valid())
        (form_data['end_month'], form_data['period']) = (1, 12)
        form = FiscalYearForm(data=form_data)
        self.assertFalse(form.is_valid())
        (form_data['end_month'], form_data['period']) = (3, 12)
        form = FiscalYearForm(data=form_data)
        self.assertFalse(form.is_valid())

        (form_data['end_month'], form_data['period']) = (3, 13)
        form = FiscalYearForm(data=form_data)
        self.assertFalse(form.is_valid())
        (form_data['end_month'], form_data['period']) = (1, 13)
        form = FiscalYearForm(data=form_data)
        self.assertFalse(form.is_valid())
        (form_data['end_month'], form_data['period']) = (4, 13)
        form = FiscalYearForm(data=form_data)
        self.assertFalse(form.is_valid())

    def test_valid_period_change_13_to_12(self):
        '''
        A ``FiscalYear`` can switch from a previous ``period`` of ``13`` to
        a new ``period`` of ``12`` only if there are no ``Transactions`` in
        the previous Year's ``end_month``.
        '''
        FiscalYear.objects.create(year=2012, end_month=2, period=13)
        form_data = {
                'year': 2013,
                'end_month': 2,
                'period': 12
        }
        form = FiscalYearForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_valid_period_change_13_to_12_fail(self):
        '''
        A ``FiscalYear`` cannot switch from a previous ``period`` of ``13`` to
        a new ``period`` of ``12`` only if there are ``Transactions`` in the
        previous Year's ``end_month``.
        '''
        FiscalYear.objects.create(year=2012, end_month=2, period=13)
        asset_header = create_header('asset', cat_type=1)
        asset_acc = create_account('asset', asset_header, 0, 1)
        entry = create_entry(datetime.date(2012, 2, 1), 'Entry')
        create_transaction(entry, asset_acc, -20)
        create_transaction(entry, asset_acc, 20)

        form_data = {
                'year': 2013,
                'end_month': 2,
                'period': 12
        }
        form = FiscalYearForm(data=form_data)
        self.assertFalse(form.is_valid())

    def test_no_earnings_accounts_fail(self):
        '''
        A FiscalYear is invalid if ``Current Year Earnings`` and
        ``Retained Earnings`` Equity(type=3) ``Accounts`` do not exist and
        there are previous ``FiscalYears``.
        '''
        Account.objects.all().delete()
        FiscalYear.objects.create(year=2000, end_month=4, period=12)
        form_data = {
                'year': 2001,
                'end_month': 4,
                'period': 12
        }
        form = FiscalYearForm(data=form_data)
        self.assertFalse(form.is_valid())


class FiscalYearAccountsFormSetTests(TestCase):
    '''
    Test the FiscalYearAccountsForm initial data.
    '''
    def setUp(self):
        self.asset_header = create_header('asset', cat_type=1)
        self.asset_account = create_account('asset', self.asset_header, 0, 1)

    def test_unreconciled_account_initial(self):
        '''
        An Account that is unreconciled should have it's initial ``exclude``
        value unchecked.
        '''
        formset = FiscalYearAccountsFormSet()
        self.assertFalse(formset.forms[0].fields['exclude'].initial)

    def test_reconciled_account_initial(self):
        '''
        A reconciled Account will have its initial ``exclude`` value checked.
        '''
        self.asset_account.last_reconciled = datetime.date.today()
        self.asset_account.save()
        formset = FiscalYearAccountsFormSet()
        self.assertTrue(formset.forms[0].fields['exclude'].initial)

    def test_old_reconciled_account_initial(self):
        '''
        An Account reconciled a long time ago will also have it's initial
        ``exclude`` value checked.
        '''
        self.asset_account.last_reconciled = datetime.date.today() - datetime.timedelta(days=1000)
        self.asset_account.save()
        formset = FiscalYearAccountsFormSet()
        self.assertTrue(formset.forms[0].fields['exclude'].initial)


class QuickSearchViewTests(TestCase):
    '''
    Test views for redirecting dropdowns to Account details or a Bank Account's
    register
    '''
    def setUp(self):
        '''
        An Account and Bank Account are required the respective searches
        '''
        self.asset_header = create_header('asset', cat_type=1)
        self.liability_header = create_header('liability', cat_type=2)
        self.bank_account = create_account('bank', self.asset_header, 0, 1, True)
        self.liability_account = create_account('liability', self.liability_header, 0, 2)
        self.event = Event.objects.create(name='test event', number='1', date=datetime.date.today(),
                                          city='mineral', state='VA')

    def test_quick_account_success(self):
        '''
        A `GET` to the `quick_account_search` view with an `account` should
        redirect to the Account's detail page.
        '''
        response = self.client.get(reverse('accounts.views.quick_account_search'),
                                   data={'account': self.liability_account.id})

        self.assertRedirects(response, reverse('accounts.views.show_account_detail', args=[self.liability_account.slug]))

    def test_quick_account_fail_not_account(self):
        '''
        A `GET` to the `quick_account_search` view with an `account` should
        return a 404 if the Account does not exist.
        '''
        response = self.client.get(reverse('accounts.views.quick_account_search'),
                                   data={'account': 9001})

        self.assertEqual(response.status_code, 404)

    def test_quick_account_fail_no_account(self):
        '''
        A `GET` to the `quick_account_search` view with no `account` should
        return a 404.
        '''
        response = self.client.get(reverse('accounts.views.quick_account_search'))
        self.assertEqual(response.status_code, 404)

    def test_quick_bank_success(self):
        '''
        A `GET` to the `quick_bank_search` view with a `bank` should
        redirect to the Account's register page.
        '''
        response = self.client.get(reverse('accounts.views.quick_bank_search'),
                                   data={'bank': self.bank_account.id})

        self.assertRedirects(response, reverse('accounts.views.bank_register', args=[self.bank_account.slug]))

    def test_quick_bank_fail_not_bank(self):
        '''
        A `GET` to the `quick_bank_search` view with a `bank` should
        return a 404 if the Account is not a bank.
        '''
        response = self.client.get(reverse('accounts.views.quick_bank_search'),
                                   data={'bank': self.liability_account.id})

        self.assertEqual(response.status_code, 404)

    def test_quick_bank_fail_not_account(self):
        '''
        A `GET` to the `quick_bank_search` view with a `bank` should
        return a 404 if the Account does not exist.
        '''
        response = self.client.get(reverse('accounts.views.quick_bank_search'),
                                   data={'bank': 9001})

        self.assertEqual(response.status_code, 404)

    def test_quick_bank_fail_no_bank(self):
        '''
        A `GET` to the `quick_bank_search` view with no `bank` should return
        a 404.
        '''
        response = self.client.get(reverse('accounts.views.quick_bank_search'))
        self.assertEqual(response.status_code, 404)

    def test_quick_event_success(self):
        '''
        A `GET` to the `quick_event_search` view with an `event_id` should
        redirect to the Event's Detail page.
        '''
        response = self.client.get(reverse('accounts.views.quick_event_search'),
                                   data={'event': self.event.id})
        self.assertRedirects(response, reverse('accounts.views.show_event_detail', args=[self.event.id]))

    def test_quick_event_fail_not_event(self):
        '''
        A `GET` to the `quick_event_search` view with an `event_id` should
        return a 404 if the Event does not exist.
        '''
        response = self.client.get(reverse('accounts.views.quick_event_search'),
                                   data={'event': 9001})
        self.assertEqual(response.status_code, 404)

    def test_quick_event_fail_no_event(self):
        '''
        A `GET` to the `quick_event_search` view with no `event_id` should return
        a 404.
        '''
        response = self.client.get(reverse('accounts.views.quick_event_search'))
        self.assertEqual(response.status_code, 404)


class AccountChartViewTests(TestCase):
    '''
    Test Account Chart display and Header child displays
    '''
    def setUp(self):
        self.asset_header = create_header('asset', cat_type=1)
        self.asset_child_header = create_header('asset child', parent=self.asset_header, cat_type=1)
        self.expense_header = create_header('expense', cat_type=6)
        self.expense_child_header = create_header('expense child', parent=self.expense_header, cat_type=6)

    def test_show_chart_initial(self):
        '''
        A `GET` to the `show_accounts_chart` view should return the Header tree.
        '''
        response = self.client.get(reverse('accounts.views.show_accounts_chart'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/account_charts.html')
        self.assertNotIn('header', response.context)
        self.assertItemsEqual(response.context['nodes'],
                              Header.objects.order_by('id'))

    def test_show_chart_header_success(self):
        '''
        A `GET` to the `show_accounts_chart` view with a `header_slug` should
        retrieve the Header and it's children.
        '''
        response = self.client.get(reverse('accounts.views.show_accounts_chart',
                                           kwargs={'header_slug': self.asset_header.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['header'], self.asset_header)
        self.assertItemsEqual(response.context['nodes'],
                              [self.asset_header, self.asset_child_header])

    def test_show_chart_header_fail(self):
        '''
        A `GET` to the `show_accounts_chart` view with an invalid `header_slug`
        should return a 404.
        '''
        response = self.client.get(reverse('accounts.views.show_accounts_chart',
                                           kwargs={'header_slug': 'does-not-exist'}))
        self.assertEqual(response.status_code, 404)


class AccountReconcileViewTests(TestCase):
    '''
    Test the `reconcile_account` view
    '''
    def setUp(self):
        '''
        Test Accounts with `flip_balance` of `True`(asset/bank) and `False`(liability).
        '''
        self.asset_header = create_header('asset', cat_type=1)
        self.liability_header = create_header('liability', cat_type=2)
        self.bank_account = create_account('bank', self.asset_header, 0, 1, True)
        self.liability_account = create_account('liability', self.liability_header, 0, 2)

    def test_reconcile_account_view_initial(self):
        '''
        A `GET` to the `reconcile_account` view with an `account_slug` should
        return an AccountReconcile Form for that Account.
        '''
        response = self.client.get(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}))

        self.assertEqual(response.status_code, 200)
        self.failUnless(isinstance(response.context['account_form'], AccountReconcileForm))
        self.assertNotIn('transaction_formset', response.context)
        self.assertTemplateUsed(response, 'accounts/account_reconcile.html')
        self.assertEqual(response.context['account'], self.bank_account)
        self.assertEqual(response.context['last_reconciled'], self.bank_account.last_reconciled)
        self.assertEqual(response.context['reconciled_balance'], 0)

    def test_reconcile_account_view_initial_account_slug_fail(self):
        '''
        A `GET` to the `reconcile_account` view with an invalid `account_slug`
        should return a 404.
        '''
        response = self.client.get(reverse('accounts.views.reconcile_account', kwargs={'account_slug': 'I-dont-exist'}))
        self.assertEqual(response.status_code, 404)

    def test_reconcile_account_view_initial_post_account_slug_fail(self):
        '''
        A `POST` to the `reconcile_account` view with an invalid `account_slug`
        should return a 404.
        '''
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': 'I-dont-exist'}))
        self.assertEqual(response.status_code, 404)

    def test_reconcile_account_view_get_transactions(self):
        '''
        A `POST` to the `reconcile_account` view with a `statement_date`,
        `statement_balance` and submit value of `Get Transactions` should return
        the bound AccountReconcile Form and a ReconcileTransactionFormSet containing
        the Account's unreconciled Transactions from between the Account's
        `last_reconciled` date and the `statement_date`.
        '''
        past_entry = create_entry(datetime.date.today() - datetime.timedelta(days=60), 'before reconciled date entry')
        past_bank_tran = create_transaction(past_entry, self.bank_account, 100)
        create_transaction(past_entry, self.liability_account, -100)

        entry = create_entry(datetime.date.today(), 'between reconciled date and statement date')
        Transaction.objects.create(journal_entry=entry, account=self.bank_account, balance_delta=50, reconciled=True)
        bank_tran = create_transaction(entry, self.bank_account, 50)
        create_transaction(entry, self.liability_account, -100)

        future_entry = create_entry(datetime.date.today() + datetime.timedelta(days=30), 'past statement date entry')
        create_transaction(future_entry, self.bank_account, 100)
        create_transaction(future_entry, self.liability_account, -100)

        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today(),
                                          'account-statement_balance': '50',
                                          'submit': 'Get Transactions'})
        self.assertEqual(response.status_code, 200)
        self.failUnless(isinstance(response.context['account_form'], AccountReconcileForm))
        self.failUnless(response.context['account_form'].is_bound)
        self.failUnless(isinstance(response.context['transaction_formset'], ReconcileTransactionFormSet))
        self.assertEqual(len(response.context['transaction_formset'].forms), 2)
        self.assertEqual(response.context['transaction_formset'].forms[0].instance, past_bank_tran)
        self.assertEqual(response.context['transaction_formset'].forms[1].instance, bank_tran)

    def test_reconcile_account_view_get_transactions_fail_old_statement_date(self):
        '''
        A `POST` to the `reconcile_account` view with a `statement_date` before
        the Accounts last_reconciled date will return an Error and no Transactions.
        '''
        self.bank_account.last_reconciled = datetime.date.today()
        self.bank_account.save()
        past_entry = create_entry(datetime.date.today() - datetime.timedelta(days=60), 'before reconciled date entry')
        create_transaction(past_entry, self.bank_account, 100)
        create_transaction(past_entry, self.liability_account, -100)

        entry = create_entry(datetime.date.today(), 'between reconciled date and statement date')
        Transaction.objects.create(journal_entry=entry, account=self.bank_account, balance_delta=50, reconciled=True)
        create_transaction(entry, self.bank_account, 50)
        create_transaction(entry, self.liability_account, -100)

        future_entry = create_entry(datetime.date.today() + datetime.timedelta(days=30), 'past statement date entry')
        create_transaction(future_entry, self.bank_account, 100)
        create_transaction(future_entry, self.liability_account, -100)

        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today() - datetime.timedelta(days=365),
                                          'account-statement_balance': '50',
                                          'submit': 'Get Transactions'})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'account_form', 'statement_date', 'Must be later than the Last Reconciled Date')
        self.assertNotIn('transaction_formset', response.context)

    def test_reconcile_account_view_flip_success_neg_statement_zero_reconciled(self):
        '''
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of True, `statement_amount` < 0  and
        a `reconciled_amount` of 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        '''
        entry = create_entry(datetime.date.today(), 'test memo')
        create_transaction(entry, self.bank_account, -50)
        create_transaction(entry, self.bank_account, -50)
        create_transaction(entry, self.bank_account, 275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=5),
                                          'account-statement_balance': '-175',
                                          'form-TOTAL_FORMS': 3,
                                          'form-INITIAL_FORMS': 3,
                                          'form-0-id': 1,
                                          'form-0-reconciled': True,
                                          'form-1-id': 2,
                                          'form-1-reconciled': True,
                                          'form-2-id': 3,
                                          'form-2-reconciled': True,
                                          'submit': 'Reconcile Transactions'})
        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.bank_account.slug}))
        self.assertTrue(Transaction.objects.all()[0].reconciled)
        self.assertTrue(Transaction.objects.all()[1].reconciled)
        self.assertTrue(Transaction.objects.all()[2].reconciled)

    def test_reconcile_account_view_flip_success_zero_statement_zero_reconciled(self):
        '''
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of True, `statement_amount` of 0  and
        a `reconciled_amount` of 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        '''
        entry = create_entry(datetime.date.today(), 'test memo')
        create_transaction(entry, self.bank_account, -50)
        create_transaction(entry, self.bank_account, 50)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=5),
                                          'account-statement_balance': '0',
                                          'form-TOTAL_FORMS': 2,
                                          'form-INITIAL_FORMS': 2,
                                          'form-0-id': 1,
                                          'form-0-reconciled': True,
                                          'form-1-id': 2,
                                          'form-1-reconciled': True,
                                          'submit': 'Reconcile Transactions'})

        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.bank_account.slug}))
        self.assertTrue(Transaction.objects.all()[0].reconciled)
        self.assertTrue(Transaction.objects.all()[1].reconciled)

    def test_reconcile_account_view_flip_success_pos_statement_zero_reconciled(self):
        '''
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of True, `statement_amount` > 0  and
        a `reconciled_amount` of 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        '''
        entry = create_entry(datetime.date.today(), 'test memo')
        create_transaction(entry, self.bank_account, -275)
        create_transaction(entry, self.liability_account, 275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=5),
                                          'account-statement_balance': '275',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': 1,
                                          'form-0-reconciled': True,
                                          'submit': 'Reconcile Transactions'})

        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.bank_account.slug}))
        self.assertTrue(Transaction.objects.all()[0].reconciled)
        self.assertFalse(Transaction.objects.all()[1].reconciled)

    def test_reconcile_account_view_flip_success_neg_statement_neg_reconciled(self):
        '''
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of True, `statement_amount` < 0  and
        a `reconciled_balance` < 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        '''
        self.test_reconcile_account_view_flip_success_neg_statement_zero_reconciled()
        entry = create_entry(datetime.date.today() + datetime.timedelta(days=7), 'test memo')
        create_transaction(entry, self.bank_account, 275)
        create_transaction(entry, self.liability_account, -275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=10),
                                          'account-statement_balance': '-450',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': 4,
                                          'form-0-reconciled': True,
                                          'submit': 'Reconcile Transactions'})
        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.bank_account.slug}))
        self.assertTrue(Transaction.objects.all()[3].reconciled)
        self.assertFalse(Transaction.objects.all()[4].reconciled)

    def test_reconcile_account_view_flip_success_pos_statement_neg_reconciled(self):
        '''
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of True, `statement_amount` > 0  and
        a `reconciled_balance` < 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        '''
        self.test_reconcile_account_view_flip_success_neg_statement_zero_reconciled()
        entry = create_entry(datetime.date.today() + datetime.timedelta(days=7), 'test memo')
        create_transaction(entry, self.bank_account, -275)
        create_transaction(entry, self.liability_account, 275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=10),
                                          'account-statement_balance': '100',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': 4,
                                          'form-0-reconciled': True,
                                          'submit': 'Reconcile Transactions'})
        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.bank_account.slug}))
        self.assertTrue(Transaction.objects.all()[3].reconciled)
        self.assertFalse(Transaction.objects.all()[4].reconciled)

    def test_reconcile_account_view_flip_success_zero_statement_neg_reconciled(self):
        '''
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of True, `statement_amount` of 0  and
        a `reconciled_balance` < 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        '''
        self.test_reconcile_account_view_flip_success_neg_statement_zero_reconciled()
        entry = create_entry(datetime.date.today() + datetime.timedelta(days=7), 'test memo')
        create_transaction(entry, self.bank_account, -175)
        create_transaction(entry, self.liability_account, 275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=10),
                                          'account-statement_balance': '0',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': 4,
                                          'form-0-reconciled': True,
                                          'submit': 'Reconcile Transactions'})
        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.bank_account.slug}))
        self.assertTrue(Transaction.objects.all()[3].reconciled)
        self.assertFalse(Transaction.objects.all()[4].reconciled)

    def test_reconcile_account_view_flip_success_neg_statement_pos_reconciled(self):
        '''
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of True, `statement_amount` < 0  and
        a `reconciled_balance` < 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        '''
        self.test_reconcile_account_view_flip_success_pos_statement_zero_reconciled()
        entry = create_entry(datetime.date.today() + datetime.timedelta(days=7), 'test memo')
        create_transaction(entry, self.bank_account, 375)
        create_transaction(entry, self.liability_account, -275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=10),
                                          'account-statement_balance': '-100',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': 3,
                                          'form-0-reconciled': True,
                                          'submit': 'Reconcile Transactions'})
        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.bank_account.slug}))
        self.assertTrue(Transaction.objects.all()[2].reconciled)
        self.assertFalse(Transaction.objects.all()[3].reconciled)

    def test_reconcile_account_view_flip_success_pos_statement_pos_reconciled(self):
        '''
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of True, `statement_amount` > 0  and
        a `reconciled_balance` < 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        '''
        self.test_reconcile_account_view_flip_success_pos_statement_zero_reconciled()
        entry = create_entry(datetime.date.today() + datetime.timedelta(days=7), 'test memo')
        create_transaction(entry, self.bank_account, 175)
        create_transaction(entry, self.liability_account, 275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=10),
                                          'account-statement_balance': '100',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': 3,
                                          'form-0-reconciled': True,
                                          'submit': 'Reconcile Transactions'})
        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.bank_account.slug}))
        self.assertTrue(Transaction.objects.all()[2].reconciled)
        self.assertFalse(Transaction.objects.all()[3].reconciled)

    def test_reconcile_account_view_flip_success_zero_statement_pos_reconciled(self):
        '''
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of True, `statement_amount` of 0  and
        a `reconciled_balance` < 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        '''
        self.test_reconcile_account_view_flip_success_neg_statement_zero_reconciled()
        entry = create_entry(datetime.date.today() + datetime.timedelta(days=7), 'test memo')
        create_transaction(entry, self.bank_account, -175)
        create_transaction(entry, self.liability_account, 275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=10),
                                          'account-statement_balance': '0',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': 4,
                                          'form-0-reconciled': True,
                                          'submit': 'Reconcile Transactions'})
        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.bank_account.slug}))
        self.assertTrue(Transaction.objects.all()[3].reconciled)
        self.assertFalse(Transaction.objects.all()[4].reconciled)

    def test_reconcile_account_view_no_flip_success_neg_statement_zero_reconciled(self):
        '''
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of False, `statement_amount` < 0  and
        a `reconciled_amount` of 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        '''
        entry = create_entry(datetime.date.today(), 'test memo')
        create_transaction(entry, self.liability_account, 50)
        create_transaction(entry, self.liability_account, 50)
        create_transaction(entry, self.liability_account, -275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.liability_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=5),
                                          'account-statement_balance': '-175',
                                          'form-TOTAL_FORMS': 3,
                                          'form-INITIAL_FORMS': 3,
                                          'form-0-id': 1,
                                          'form-0-reconciled': True,
                                          'form-1-id': 2,
                                          'form-1-reconciled': True,
                                          'form-2-id': 3,
                                          'form-2-reconciled': True,
                                          'submit': 'Reconcile Transactions'})

        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.liability_account.slug}))
        self.assertTrue(Transaction.objects.all()[0].reconciled)
        self.assertTrue(Transaction.objects.all()[1].reconciled)
        self.assertTrue(Transaction.objects.all()[2].reconciled)

    def test_reconcile_account_view_no_flip_success_zero_statement_zero_reconciled(self):
        '''
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of False, `statement_amount` of 0  and
        a `reconciled_amount` of 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        '''
        entry = create_entry(datetime.date.today(), 'test memo')
        create_transaction(entry, self.liability_account, -50)
        create_transaction(entry, self.liability_account, 50)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.liability_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=5),
                                          'account-statement_balance': '0',
                                          'form-TOTAL_FORMS': 2,
                                          'form-INITIAL_FORMS': 2,
                                          'form-0-id': 1,
                                          'form-0-reconciled': True,
                                          'form-1-id': 2,
                                          'form-1-reconciled': True,
                                          'submit': 'Reconcile Transactions'})

        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.liability_account.slug}))
        self.assertTrue(Transaction.objects.all()[0].reconciled)
        self.assertTrue(Transaction.objects.all()[1].reconciled)

    def test_reconcile_account_view_no_flip_success_pos_statement_zero_reconciled(self):
        '''
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of False, `statement_amount` > 0  and
        a `reconciled_amount` of 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        '''
        entry = create_entry(datetime.date.today(), 'test memo')
        create_transaction(entry, self.bank_account, -275)
        create_transaction(entry, self.liability_account, 275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.liability_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=5),
                                          'account-statement_balance': '275',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': 2,
                                          'form-0-reconciled': True,
                                          'submit': 'Reconcile Transactions'})

        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.liability_account.slug}))
        self.assertTrue(Transaction.objects.all()[1].reconciled)
        self.assertFalse(Transaction.objects.all()[0].reconciled)

    def test_reconcile_account_view_no_flip_success_neg_statement_neg_reconciled(self):
        '''
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of False, `statement_amount` < 0  and
        a `reconciled_balance` < 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        '''
        self.test_reconcile_account_view_no_flip_success_neg_statement_zero_reconciled()
        entry = create_entry(datetime.date.today() + datetime.timedelta(days=7), 'test memo')
        create_transaction(entry, self.bank_account, 275)
        create_transaction(entry, self.liability_account, -275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.liability_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=10),
                                          'account-statement_balance': '-450',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': 5,
                                          'form-0-reconciled': True,
                                          'submit': 'Reconcile Transactions'})
        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.liability_account.slug}))
        self.assertTrue(Transaction.objects.all()[4].reconciled)
        self.assertFalse(Transaction.objects.all()[3].reconciled)

    def test_reconcile_account_view_no_flip_success_pos_statement_neg_reconciled(self):
        '''
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of False, `statement_amount` > 0  and
        a `reconciled_balance` < 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        '''
        self.test_reconcile_account_view_no_flip_success_neg_statement_zero_reconciled()
        entry = create_entry(datetime.date.today() + datetime.timedelta(days=7), 'test memo')
        create_transaction(entry, self.bank_account, -275)
        create_transaction(entry, self.liability_account, 275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.liability_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=10),
                                          'account-statement_balance': '100',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': 5,
                                          'form-0-reconciled': True,
                                          'submit': 'Reconcile Transactions'})
        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.liability_account.slug}))
        self.assertTrue(Transaction.objects.all()[4].reconciled)
        self.assertFalse(Transaction.objects.all()[3].reconciled)

    def test_reconcile_account_view_no_flip_success_zero_statement_neg_reconciled(self):
        '''
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of False, `statement_amount` of 0  and
        a `reconciled_balance` < 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        '''
        self.test_reconcile_account_view_no_flip_success_neg_statement_zero_reconciled()
        entry = create_entry(datetime.date.today() + datetime.timedelta(days=7), 'test memo')
        create_transaction(entry, self.bank_account, -175)
        create_transaction(entry, self.liability_account, 175)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.liability_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=10),
                                          'account-statement_balance': '0',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': 5,
                                          'form-0-reconciled': True,
                                          'submit': 'Reconcile Transactions'})
        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.liability_account.slug}))
        self.assertTrue(Transaction.objects.all()[4].reconciled)
        self.assertFalse(Transaction.objects.all()[3].reconciled)

    def test_reconcile_account_view_no_flip_success_neg_statement_pos_reconciled(self):
        '''
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of False, `statement_amount` < 0  and
        a `reconciled_balance` < 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        '''
        self.test_reconcile_account_view_no_flip_success_pos_statement_zero_reconciled()
        entry = create_entry(datetime.date.today() + datetime.timedelta(days=7), 'test memo')
        create_transaction(entry, self.bank_account, 375)
        create_transaction(entry, self.liability_account, -375)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.liability_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=10),
                                          'account-statement_balance': '-100',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': 4,
                                          'form-0-reconciled': True,
                                          'submit': 'Reconcile Transactions'})
        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.liability_account.slug}))
        self.assertTrue(Transaction.objects.all()[3].reconciled)
        self.assertFalse(Transaction.objects.all()[2].reconciled)

    def test_reconcile_account_view_no_flip_success_pos_statement_pos_reconciled(self):
        '''
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of False, `statement_amount` > 0  and
        a `reconciled_balance` < 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        '''
        self.test_reconcile_account_view_no_flip_success_pos_statement_zero_reconciled()
        entry = create_entry(datetime.date.today() + datetime.timedelta(days=7), 'test memo')
        create_transaction(entry, self.bank_account, 275)
        create_transaction(entry, self.liability_account, 275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.liability_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=10),
                                          'account-statement_balance': '550',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': 4,
                                          'form-0-reconciled': True,
                                          'submit': 'Reconcile Transactions'})
        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.liability_account.slug}))
        self.assertTrue(Transaction.objects.all()[3].reconciled)
        self.assertFalse(Transaction.objects.all()[2].reconciled)

    def test_reconcile_account_view_no_flip_success_zero_statement_pos_reconciled(self):
        '''
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of False, `statement_amount` of 0  and
        a `reconciled_balance` < 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        '''
        self.test_reconcile_account_view_no_flip_success_pos_statement_zero_reconciled()
        entry = create_entry(datetime.date.today() + datetime.timedelta(days=7), 'test memo')
        create_transaction(entry, self.bank_account, 275)
        create_transaction(entry, self.liability_account, -275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.liability_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=10),
                                          'account-statement_balance': '0',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': 4,
                                          'form-0-reconciled': True,
                                          'submit': 'Reconcile Transactions'})
        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.liability_account.slug}))
        self.assertTrue(Transaction.objects.all()[3].reconciled)
        self.assertFalse(Transaction.objects.all()[2].reconciled)

    def test_reconcile_account_view_fail_invalid_form_data(self):
        '''
        A `POST` to the `reconcile_account` view with an invalid data
        should return forms with errors.
        '''
        entry = create_entry(datetime.date.today(), 'test memo')
        create_transaction(entry, self.bank_account, -275)
        create_transaction(entry, self.liability_account, 275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=5),
                                          'account-statement_balance': 'arg',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': 1,
                                          'form-0-reconciled': 'over 9000',
                                          'submit': 'Reconcile Transactions'})

        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'account_form', 'statement_balance',
                'Enter a number.')

    def test_reconcile_account_view_fail_no_submit(self):
        '''
        A `POST` to the `reconcile_account` view with no value for `submit` should
        return a 404.
        '''
        entry = create_entry(datetime.date.today(), 'test memo')
        create_transaction(entry, self.bank_account, -275)
        create_transaction(entry, self.liability_account, 275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=5),
                                          'account-statement_balance': '275',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': 1,
                                          'form-0-reconciled': True})
        self.assertEqual(response.status_code, 404)

    def test_reconcile_account_view_fail_invalid_submit(self):
        '''
        A `POST` to the `reconcile_account` view with an invalid `submit` value
        should return a 404.
        '''
        entry = create_entry(datetime.date.today(), 'test memo')
        create_transaction(entry, self.bank_account, -275)
        create_transaction(entry, self.liability_account, 275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=5),
                                          'account-statement_balance': '275',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': 1,
                                          'form-0-reconciled': True,
                                          'submit': 'this button doesnt exist'})
        self.assertEqual(response.status_code, 404)

    def test_reconcile_account_view_fail_old_statement_date(self):
        '''
        A `POST` to the `reconcile_account` view with valid Transaction data
        but a `statement_date` before the Accounts last_reconciled date will
        return an Error and the Transactions.
        '''
        self.bank_account.last_reconciled = datetime.date.today()
        self.bank_account.save()
        entry = create_entry(datetime.date.today(), 'test memo')
        create_transaction(entry, self.bank_account, -50)
        create_transaction(entry, self.bank_account, -50)
        create_transaction(entry, self.bank_account, 275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today() - datetime.timedelta(days=500),
                                          'account-statement_balance': '-175',
                                          'form-TOTAL_FORMS': 3,
                                          'form-INITIAL_FORMS': 3,
                                          'form-0-id': 1,
                                          'form-0-reconciled': True,
                                          'form-1-id': 2,
                                          'form-1-reconciled': True,
                                          'form-2-id': 3,
                                          'form-2-reconciled': True,
                                          'submit': 'Reconcile Transactions'})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'account_form', 'statement_date', 'Must be later than the Last Reconciled Date')
        self.assertIn('transaction_formset', response.context)

    def test_reconcile_account_view_fail_statement_out_of_balance_flip(self):
        '''
        A `POST` to the `reconcile_account` view with an out of balance statement
        will not mark the Transactions as Reconciled and return an out of balance
        error for Accounts where `flip_balance` is `True`.
        '''
        entry = create_entry(datetime.date.today(), 'test memo')
        create_transaction(entry, self.bank_account, 50)
        create_transaction(entry, self.bank_account, 50)
        create_transaction(entry, self.liability_account, -100)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today(),
                                          'account-statement_balance': '75',
                                          'form-TOTAL_FORMS': 2,
                                          'form-INITIAL_FORMS': 2,
                                          'form-0-id': 1,
                                          'form-0-reconciled': True,
                                          'form-1-id': 2,
                                          'form-1-reconciled': True,
                                          'submit': 'Reconcile Transactions'})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.all()[0].reconciled)
        self.assertFalse(Transaction.objects.all()[1].reconciled)
        self.assertEqual(response.context['transaction_formset'].non_form_errors()[0],
                         'Reconciled Transactions and Bank Statement are out of balance.')

    def test_reconcile_account_view_fail_transaction_out_of_balance_flip(self):
        '''
        A `POST` to the `reconcile_account` view with out of balance Transactions
        will not mark the Transactions as Reconciled and return an out of balance
        error for Accounts where `flip_balance` is `True`.
        '''
        entry = create_entry(datetime.date.today(), 'test memo')
        create_transaction(entry, self.bank_account, 50)
        create_transaction(entry, self.bank_account, 50)
        create_transaction(entry, self.liability_account, -100)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today(),
                                          'account-statement_balance': '100',
                                          'form-TOTAL_FORMS': 2,
                                          'form-INITIAL_FORMS': 2,
                                          'form-0-id': 1,
                                          'form-0-reconciled': True,
                                          'form-1-id': 2,
                                          'form-1-reconciled': False,
                                          'submit': 'Reconcile Transactions'})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.all()[0].reconciled)
        self.assertFalse(Transaction.objects.all()[1].reconciled)
        self.assertEqual(response.context['transaction_formset'].non_form_errors()[0],
                         'Reconciled Transactions and Bank Statement are out of balance.')

    def test_reconcile_account_view_fail_statement_out_of_balance_no_flip(self):
        '''
        A `POST` to the `reconcile_account` view with an out of balance statement
        will not mark the Transactions as Reconciled and return an out of balance
        error.
        '''
        entry = create_entry(datetime.date.today(), 'test memo')
        create_transaction(entry, self.bank_account, 50)
        create_transaction(entry, self.bank_account, 50)
        create_transaction(entry, self.liability_account, -50)
        create_transaction(entry, self.liability_account, -50)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.liability_account.slug}),
                                    data={'account-statement_date': datetime.date.today(),
                                          'account-statement_balance': '75',
                                          'form-TOTAL_FORMS': 2,
                                          'form-INITIAL_FORMS': 2,
                                          'form-0-id': 3,
                                          'form-0-reconciled': True,
                                          'form-1-id': 4,
                                          'form-1-reconciled': True,
                                          'submit': 'Reconcile Transactions'})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.all()[2].reconciled)
        self.assertFalse(Transaction.objects.all()[3].reconciled)
        self.assertEqual(response.context['transaction_formset'].non_form_errors()[0],
                         'Reconciled Transactions and Bank Statement are out of balance.')

    def test_reconcile_account_view_fail_transaction_out_of_balance_no_flip(self):
        '''
        A `POST` to the `reconcile_account` view with out of balance Transactions
        will not mark the Transactions as Reconciled and return an out of balance
        error.
        '''
        entry = create_entry(datetime.date.today(), 'test memo')
        create_transaction(entry, self.bank_account, 50)
        create_transaction(entry, self.bank_account, 50)
        create_transaction(entry, self.liability_account, -50)
        create_transaction(entry, self.liability_account, -50)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.liability_account.slug}),
                                    data={'account-statement_date': datetime.date.today(),
                                          'account-statement_balance': '100',
                                          'form-TOTAL_FORMS': 2,
                                          'form-INITIAL_FORMS': 2,
                                          'form-0-id': 3,
                                          'form-0-reconciled': True,
                                          'form-1-id': 4,
                                          'form-1-reconciled': False,
                                          'submit': 'Reconcile Transactions'})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.all()[2].reconciled)
        self.assertFalse(Transaction.objects.all()[3].reconciled)
        self.assertEqual(response.context['transaction_formset'].non_form_errors()[0],
                         'Reconciled Transactions and Bank Statement are out of balance.')

    def test_reconcile_account_view_change_last_reconciled_date(self):
        '''
        A successful Reconciliation should cause the `last_reconciled` and `reconciled_balance`
        variables to change
        '''
        self.test_reconcile_account_view_flip_success_neg_statement_zero_reconciled()
        response = self.client.get(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['last_reconciled'], datetime.date.today() + datetime.timedelta(days=5))
        self.assertEqual(Account.objects.get(bank=True).last_reconciled, datetime.date.today() + datetime.timedelta(days=5))
        self.assertEqual(response.context['reconciled_balance'], -175)


class AccountDetailViewTests(TestCase):
    '''
    Test Account detail view
    '''
    def setUp(self):
        self.asset_header = create_header('asset', cat_type=1)
        self.liability_header = create_header('liability', cat_type=2)
        self.bank_account = create_account('bank', self.asset_header, 0, 1, True)
        self.liability_account = create_account('liability', self.liability_header, 0, 2)

    def test_show_account_detail_view_initial(self):
        '''
        A `GET` to the `show_account_detail` view with an `account_slug` should
        return a DateRangeForm, start and stopdate from the 1st of Month to
        Today, an Account and all Transactions within the initial range.
        The balance counters `startbalance`, `endbalance`, `net_change`,
        `debit_total` and `credit_total` should also be returned and flipped if
        neccessary.
        '''
        in_range_date = datetime.date.today()
        out_range_date = datetime.date(in_range_date.year + 20, 1, 1)
        out_range_date2 = datetime.date(in_range_date.year - 20, 1, 1)
        date_range = (datetime.date(in_range_date.year, in_range_date.month, 1), in_range_date)

        # In range entries
        general = create_entry(in_range_date, 'general entry')
        tran_general = create_transaction(general, self.bank_account, -100)

        banktran_receive = Transaction.objects.create(account=self.bank_account, balance_delta=-20)
        BankReceivingEntry.objects.create(main_transaction=banktran_receive, date=in_range_date, memo='receive entry',
                                     payor='test payor')
        banktran_spend = Transaction.objects.create(account=self.bank_account, balance_delta=50)
        BankSpendingEntry.objects.create(main_transaction=banktran_spend, date=in_range_date, memo='spend entry',
                                                 ach_payment=True, payee='test payee')
        # Out of range entries
        out_general = create_entry(out_range_date, 'oor general entry')
        create_transaction(out_general, self.bank_account, -70)
        out_tran1 = Transaction.objects.create(account=self.bank_account, balance_delta=-20)
        BankReceivingEntry.objects.create(main_transaction=out_tran1, date=out_range_date2, memo='older receive entry',
                                         payor='test payor')
        out_tran2 = Transaction.objects.create(account=self.bank_account, balance_delta=50)
        BankSpendingEntry.objects.create(main_transaction=out_tran2, date=out_range_date, memo='newer spend entry',
                                                     ach_payment=True, payee='test payee')

        response = self.client.get(reverse('accounts.views.show_account_detail',
                                            kwargs={'account_slug': self.bank_account.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/account_detail.html')
        self.failUnless(isinstance(response.context['form'], DateRangeForm))
        self.assertEqual(response.context['startdate'], date_range[0])
        self.assertEqual(response.context['stopdate'], date_range[1])
        self.assertEqual(response.context['account'], self.bank_account)
        self.assertSequenceEqual(response.context['transactions'], [tran_general, banktran_receive, banktran_spend])
        self.assertEqual(response.context['debit_total'], -120)
        self.assertEqual(response.context['credit_total'], 50)
        self.assertEqual(response.context['net_change'], -70)
        # These value are flipped from expected because account.flip_balance = True
        self.assertEqual(response.context['startbalance'], 20)
        self.assertEqual(response.context['endbalance'], 90)

    def test_show_account_detail_view_initial_no_transactions(self):
        '''
        A `GET` to the `show_account_detail` view with an `account_slug` for an
        Account with no Transactions should return the correct balance counters
        `startbalance`, `endbalance`, `net_change`, `debit_total` and
        `credit_total`.
        '''

    def test_show_account_detail_view_initial_only_debits(self):
        '''
        A `GET` to the `show_account_detail` view with an `account_slug` for an
        Account with only debits should return the correct balance counters
        `startbalance`, `endbalance`, `net_change`, `debit_total` and
        `credit_total`.
        '''

        general = create_entry(datetime.date.today(), 'general entry')
        create_transaction(general, self.liability_account, -100)

        response = self.client.get(reverse('accounts.views.show_account_detail',
                                            kwargs={'account_slug': self.liability_account.slug}))
        self.assertEqual(response.context['debit_total'], -100)
        self.assertEqual(response.context['credit_total'], 0)
        self.assertEqual(response.context['net_change'], -100)
        # These value are flipped from expected because account.bank = True
        self.assertEqual(response.context['startbalance'], 0)
        self.assertEqual(response.context['endbalance'], -100)

    def test_show_account_detail_view_initial_only_credits(self):
        '''
        A `GET` to the `show_account_detail` view with an `account_slug` for an
        Account with only credits should return the correct balance counters
        `startbalance`, `endbalance`, `net_change`, `debit_total` and
        `credit_total`.
        '''

        general = create_entry(datetime.date.today(), 'general entry')
        create_transaction(general, self.liability_account, 100)

        response = self.client.get(reverse('accounts.views.show_account_detail',
                                            kwargs={'account_slug': self.liability_account.slug}))
        self.assertEqual(response.context['debit_total'], 0)
        self.assertEqual(response.context['credit_total'], 100)
        self.assertEqual(response.context['net_change'], 100)
        # These value are flipped from expected because account.bank = True
        self.assertEqual(response.context['startbalance'], 0)
        self.assertEqual(response.context['endbalance'], 100)

    def test_show_account_detail_view_fail(self):
        '''
        A `GET` to the `show_account_detail` view with an invalid `account_slug`
        should return a 404 error.
        '''
        response = self.client.get(reverse('accounts.views.show_account_detail',
                                            kwargs={'account_slug': 'does-not-exist'}))
        self.assertEqual(response.status_code, 404)

    def test_show_account_detail_view_date_success(self):
        '''
        A `GET` to the `show_account_detail` view with an `account_slug`,
        startdate, and stopdate, should retrieve the Account's Transactions from
        that date period along with the respective total/change counters.
        '''
        in_range_date = datetime.date.today()
        out_range_date = datetime.date(in_range_date.year + 20, 1, 1)
        out_range_date2 = datetime.date(in_range_date.year - 20, 1, 1)
        date_range = (datetime.date(in_range_date.year, 1, 1),
                      datetime.date(in_range_date.year, 12, 31))

        # In range entries
        general = create_entry(in_range_date, 'general entry')
        tran_general = create_transaction(general, self.bank_account, -100)

        banktran_receive = Transaction.objects.create(account=self.bank_account, balance_delta=-20)
        BankReceivingEntry.objects.create(main_transaction=banktran_receive, date=in_range_date, memo='receive entry',
                                     payor='test payor')
        banktran_spend = Transaction.objects.create(account=self.bank_account, balance_delta=50)
        BankSpendingEntry.objects.create(main_transaction=banktran_spend, date=in_range_date, memo='spend entry',
                                                 ach_payment=True, payee='test payee')
        # Out of range entries
        out_general = create_entry(out_range_date, 'oor general entry')
        create_transaction(out_general, self.bank_account, -70)
        out_tran1 = Transaction.objects.create(account=self.bank_account, balance_delta=-20)
        BankReceivingEntry.objects.create(main_transaction=out_tran1, date=out_range_date2, memo='newer receive entry',
                                         payor='test payor')
        out_tran2 = Transaction.objects.create(account=self.bank_account, balance_delta=50)
        BankSpendingEntry.objects.create(main_transaction=out_tran2, date=out_range_date, memo='older spend entry',
                                                     ach_payment=True, payee='test payee')

        response = self.client.get(reverse('accounts.views.show_account_detail',
                                            kwargs={'account_slug': self.bank_account.slug}),
                                   data={'startdate': date_range[0], 'stopdate': date_range[1]})
        self.assertEqual(response.status_code, 200)
        self.failUnless(isinstance(response.context['form'], DateRangeForm))
        self.failUnless(response.context['form'].is_bound)
        self.assertEqual(response.context['startdate'], date_range[0])
        self.assertEqual(response.context['stopdate'], date_range[1])
        self.assertEqual(response.context['account'], self.bank_account)
        self.assertSequenceEqual(response.context['transactions'], [tran_general, banktran_receive, banktran_spend])
        self.assertEqual(response.context['debit_total'], -120)
        self.assertEqual(response.context['credit_total'], 50)
        self.assertEqual(response.context['net_change'], -70)
        # These value are flipped from expected because account.bank = True
        self.assertEqual(response.context['startbalance'], 20)
        self.assertEqual(response.context['endbalance'], 90)

    def test_show_account_detail_view_date_fail(self):
        '''
        A `GET` to the `show_account_detail` view with an `account_slug` and
        invalid startdate or stopdate should return a DateRangeForm with errors.
        '''
        response = self.client.get(reverse('accounts.views.show_account_detail',
                                            kwargs={'account_slug': self.bank_account.slug}),
                                   data={'startdate': '10a/2/b98', 'stopdate': '11b/1threethree7/bar'})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'startdate', 'Enter a valid date.')
        self.assertFormError(response, 'form', 'stopdate', 'Enter a valid date.')

    def test_show_account_detail_view_date_in_fiscal_year(self):
        '''
        A `GET` to the `show_account_detail` view with an `account_slug`,
        startdate, and stopdate will show the running balance and counters if
        the startdate is in the FiscalYear.
        '''
        in_range_date = datetime.date.today()
        FiscalYear.objects.create(year=in_range_date.year, end_month=12, period=12)
        date_range = (datetime.date(in_range_date.year, 1, 1),
                      datetime.date(in_range_date.year, 12, 31))

        # In range entries
        general = create_entry(in_range_date, 'general entry')
        create_transaction(general, self.bank_account, -100)

        response = self.client.get(reverse('accounts.views.show_account_detail',
                                            kwargs={'account_slug': self.bank_account.slug}),
                                   data={'startdate': date_range[0], 'stopdate': date_range[1]})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['show_balance'])

    def test_show_account_detail_view_date_no_fiscal_year(self):
        '''
        A `GET` to the `show_account_detail` view with an `account_slug`,
        startdate, and stopdate will show the running balance and counters if
        there is no current FiscalYear
        '''
        in_range_date = datetime.date.today()
        date_range = (datetime.date(in_range_date.year, 1, 1),
                      datetime.date(in_range_date.year, 12, 31))

        # In range entries
        general = create_entry(in_range_date, 'general entry')
        create_transaction(general, self.bank_account, -100)

        response = self.client.get(reverse('accounts.views.show_account_detail',
                                            kwargs={'account_slug': self.bank_account.slug}),
                                   data={'startdate': date_range[0], 'stopdate': date_range[1]})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['show_balance'])

    def test_show_account_detail_view_date_out_fiscal_year(self):
        '''
        A `GET` to the `show_account_detail` view with an `account_slug`,
        startdate, and stopdate will show the running balance and counters if
        the startdate is in the FiscalYear.
        '''
        in_range_date = datetime.date.today()
        FiscalYear.objects.create(year=in_range_date.year + 2, end_month=12, period=12)
        date_range = (datetime.date(in_range_date.year, 1, 1),
                      datetime.date(in_range_date.year, 12, 31))

        # In range entries
        general = create_entry(in_range_date, 'general entry')
        create_transaction(general, self.bank_account, -100)

        response = self.client.get(reverse('accounts.views.show_account_detail',
                                            kwargs={'account_slug': self.bank_account.slug}),
                                   data={'startdate': date_range[0], 'stopdate': date_range[1]})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['show_balance'])


class HistoricalAccountViewTests(TestCase):
    '''
    Test the `show_account_history` view.
    '''
    def test_show_account_history_view_initial_month(self):
        '''
        A `GET` to the `show_account_history` view will first try to retrieve the
        Historical Accounts for the current month in the last year.
        '''
        today = datetime.date.today()
        expense_historical = HistoricalAccount.objects.create(
             number='6-1001', name='Test Expense', type=6, amount='-900.25',
             date=datetime.date(day=1, month=today.month, year=(today.year - 1)))
        asset_historical = HistoricalAccount.objects.create(
             number='1-1001', name='Test Asset', type=1, amount='-9000.01',
             date=datetime.date(day=1, month=today.month, year=(today.year - 1)))

        response = self.client.get(reverse('accounts.views.show_account_history'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/account_history.html')
        self.assertSequenceEqual(response.context['accounts'],
                                 [asset_historical, expense_historical])

    def test_show_account_history_view_initial_recent(self):
        '''
        A `GET` to the `show_account_history` view will retrieve the Historical
        Accounts for the most recent month.
        '''
        today = datetime.date.today()
        # Most recent is ~2 1/4 years ago
        most_recent = datetime.date(day=1, month=today.month, year=today.year - 2) + datetime.timedelta(days=-93)
        expense_historical = HistoricalAccount.objects.create(
             number='6-1001', name='Test Expense', type=6, amount='-900.25',
             date=datetime.date(day=1, month=most_recent.month,
                                year=most_recent.year))
        asset_historical = HistoricalAccount.objects.create(
             number='1-1001', name='Test Asset', type=1, amount='-9000.01',
             date=datetime.date(day=1, month=most_recent.month,
                                year=most_recent.year))
        response = self.client.get(reverse('accounts.views.show_account_history'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/account_history.html')
        self.assertSequenceEqual(response.context['accounts'],
                                 [asset_historical, expense_historical])

    def test_show_account_history_view_initial_none(self):
        '''
        A `GET` to the `show_account_history` view with No Historical Accounts
        will return an appropriate message.
        '''
        response = self.client.get(reverse('accounts.views.show_account_history'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/account_history.html')
        self.assertEqual(response.context['accounts'], '')
        self.assertIn('No Account History', response.content)

    def test_show_account_history_view_by_month(self):
        '''
        A `GET` to the `show_account_history` view with a `month` and `year`
        argument will retrieve the Historical Accounts for that Month and Year
        '''
        today = datetime.date.today()
        older = today + datetime.timedelta(days=-120)
        # This would be displayed if we reversed the url with no arguments
        HistoricalAccount.objects.create(
             number='6-1001', name='Test Expense', type=6, amount='-900.25',
             date=datetime.date(day=1, month=today.month,
                                year=today.year))
        # But since we use the older date we should see only this instance.
        asset_historical = HistoricalAccount.objects.create(
             number='1-1001', name='Test Asset', type=1, amount='-9000.01',
             date=datetime.date(day=1, month=older.month,
                                year=older.year))
        response = self.client.get(reverse('accounts.views.show_account_history',
                                           kwargs={'month': older.month,
                                                   'year': older.year}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/account_history.html')
        self.assertSequenceEqual(response.context['accounts'],
                                 [asset_historical])

    def test_show_account_history_view_by_month_none(self):
        '''
        A `GET` to the `show_account_history` view with a `month` and `year`
        argument will display an error message if no Historical Accounts
        exist for the specified `month` and `year`.
        '''
        today = datetime.date.today()
        response = self.client.get(reverse('accounts.views.show_account_history',
                                           kwargs={'month': today.month,
                                                   'year': today.year}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['accounts'], '')
        self.assertIn('No Account History', response.content)

    def test_show_account_history_view_by_month_fail(self):
        '''
        A `GET` to the `show_account_history` view with an invalid `month`
        argument will return a 404 Error.
        '''
        response = self.client.get(reverse('accounts.views.show_account_history',
                                           kwargs={'month': 90,
                                                   'year': 2012}))
        self.assertEqual(response.status_code, 404)

    def test_show_account_history_view_next(self):
        '''
        A `GET` to the `show_account_history` view with `next` as a `GET`
        parameter will redirect to the next month's URL.
        '''
        today = datetime.date.today()
        next_month = today + datetime.timedelta(days=31)
        # Accessing this month with the ?next parameter...
        this_month = datetime.date(year=today.year - 1, month=today.month, day=1)
        # Will redirect to this month
        future_month = datetime.date(year=next_month.year - 1, month=next_month.month,
                                   day=1)

        HistoricalAccount.objects.create(
             number='6-1001', name='Test Expense', type=6, amount='-900.25',
             date=this_month)
        HistoricalAccount.objects.create(
             number='1-1001', name='Test Asset', type=1, amount='-9000.01',
             date=future_month)

        response = self.client.get(reverse('accounts.views.show_account_history'),
                                   data={'next': ''})
        self.assertRedirects(response, reverse('accounts.views.show_account_history',
                                               kwargs={'month': future_month.month,
                                                       'year': future_month.year}))

    def test_show_account_history_by_month_next(self):
        '''
        A `GET` to the `show_account_history` view with `month` and `year`
        arguments and `next` as a `GET` parameter will redirect to the next
        month's URL
        '''
        specific_date = datetime.date(day=1, month=11, year=2012)
        newer_date = datetime.date(day=1, month=12, year=2012)

        HistoricalAccount.objects.create(
             number='6-1001', name='Test Expense', type=6, amount='-900.25',
             date=newer_date)
        HistoricalAccount.objects.create(
             number='1-1001', name='Test Asset', type=1, amount='-9000.01',
             date=specific_date)
        response = self.client.get(reverse('accounts.views.show_account_history',
                                           kwargs={'month': specific_date.month,
                                                   'year': specific_date.year}),
                                   data={'next': ''})

        self.assertRedirects(response, reverse('accounts.views.show_account_history',
                                               kwargs={'month': newer_date.month,
                                                       'year': newer_date.year}))

    def test_show_account_history_view_next_none(self):
        '''
        A `GET` to the `show_account_history` view with `next` as a `GET`
        parameter will redirect to the same listing if there are no Historical
        Accounts for the next month.
        '''
        today = datetime.date.today()
        this_month = datetime.date(year=today.year - 1, month=today.month, day=1)
        HistoricalAccount.objects.create(
             number='6-1001', name='Test Expense', type=6, amount='-900.25',
             date=this_month)
        response = self.client.get(reverse('accounts.views.show_account_history'),
                                   data={'next': ''})
        self.assertRedirects(response,
                             reverse('accounts.views.show_account_history',
                                     kwargs={'month': this_month.month,
                                             'year': this_month.year}))

    def test_show_account_history_view_by_month_next_none(self):
        '''
        A `GET` to the `show_account_history` view with a `month` and `year`
        parameter with `next` as a `GET` parameter will redirect to the passed
        `month` and `year` if no Historical Accounts for the next `month` and
        `year` exist.
        '''
        specific_date = datetime.date(day=1, month=11, year=2012)
        HistoricalAccount.objects.create(
             number='6-1001', name='Test Expense', type=6, amount='-900.25',
             date=specific_date)
        response = self.client.get(reverse('accounts.views.show_account_history',
                                           kwargs={'month': specific_date.month,
                                                   'year': specific_date.year}),
                                   data={'next': ''})
        self.assertRedirects(response,
                             reverse('accounts.views.show_account_history',
                                      kwargs={'month': specific_date.month,
                                              'year': specific_date.year}))

    def test_show_account_history_view_previous(self):
        '''
        A `GET` to the `show_account_history` view with `previous` as a `GET`
        parameter will retrieve the Historical Accounts for the last month.
        '''
        today = datetime.date.today()
        last_month = today + datetime.timedelta(days=-31)
        # Accessing this month with the ?next parameter...
        this_month = datetime.date(year=today.year - 1, month=today.month, day=1)
        # Will redirect to this month
        past_month = datetime.date(year=last_month.year - 1,
                                   month=last_month.month, day=1)

        HistoricalAccount.objects.create(
             number='6-1001', name='Test Expense', type=6, amount='-900.25',
             date=this_month)
        HistoricalAccount.objects.create(
             number='1-1001', name='Test Asset', type=1, amount='-9000.01',
             date=past_month)

        response = self.client.get(reverse('accounts.views.show_account_history'),
                                   data={'previous': ''})
        self.assertRedirects(response, reverse('accounts.views.show_account_history',
                                               kwargs={'month': past_month.month,
                                                       'year': past_month.year}))

    def test_show_account_history_view_by_month_previous(self):
        '''
        A `GET` to the `show_account_history` view with `month` and `year`
        arguments and a `previous` `GET` parameter will redirect to the
        previous month's URL
        '''
        specific_date = datetime.date(day=1, month=11, year=2012)
        older_date = datetime.date(day=1, month=10, year=2012)

        HistoricalAccount.objects.create(
             number='6-1001', name='Test Expense', type=6, amount='-900.25',
             date=older_date)
        HistoricalAccount.objects.create(
             number='1-1001', name='Test Asset', type=1, amount='-9000.01',
             date=specific_date)
        response = self.client.get(reverse('accounts.views.show_account_history',
                                           kwargs={'month': specific_date.month,
                                                   'year': specific_date.year}),
                                   data={'previous': ''})

        self.assertRedirects(response, reverse('accounts.views.show_account_history',
                                               kwargs={'month': older_date.month,
                                                       'year': older_date.year}))

    def test_show_account_history_view_previous_none(self):
        '''
        A `GET` to the `show_account_history` view with a `month` and `year`
        parameter with `previous` as a `GET` parameter will redirect to the
        same listing if there are no Historical Accounts for the last month.
        '''
        today = datetime.date.today()
        this_month = datetime.date(year=today.year - 1, month=today.month, day=1)
        HistoricalAccount.objects.create(
             number='6-1001', name='Test Expense', type=6, amount='-900.25',
             date=this_month)
        response = self.client.get(reverse('accounts.views.show_account_history'),
                                   data={'previous': ''})
        self.assertRedirects(response,
                             reverse('accounts.views.show_account_history',
                                     kwargs={'month': this_month.month,
                                             'year': this_month.year}))

    def test_show_account_history_view_by_month_previous_none(self):
        '''
        A `GET` to the `show_account_history` view with `month` and `year`
        arguments and a `previous` `GET` parameter will display and error if
        no Historical Accounts for the last `month` and `year` exist.
        '''
        specific_date = datetime.date(day=1, month=11, year=2012)
        HistoricalAccount.objects.create(
             number='6-1001', name='Test Expense', type=6, amount='-900.25',
             date=specific_date)
        response = self.client.get(reverse('accounts.views.show_account_history',
                                           kwargs={'month': specific_date.month,
                                                   'year': specific_date.year}),
                                   data={'previous': ''})
        self.assertRedirects(response,
                             reverse('accounts.views.show_account_history',
                                      kwargs={'month': specific_date.month,
                                              'year': specific_date.year}))


class EventDetailViewTests(TestCase):
    '''
    Test Event detail view
    '''
    def setUp(self):
        '''
        Events are tied to Transactions which require an Account.
        '''
        self.asset_header = create_header('asset', cat_type=1)
        self.bank_account = create_account('bank', self.asset_header, 0, 1, True)
        self.event = Event.objects.create(name='test event', city='mineral', state='VA',
                                          date=datetime.date.today(), number=420)

    def test_show_event_detail_view_initial(self):
        '''
        A `GET` to the `show_event_detail` view with a valid `event_id` will
        return the respective `Event`.
        '''
        general = create_entry(datetime.date.today(), 'general entry')
        Transaction.objects.create(journal_entry=general, balance_delta=20, account=self.bank_account, event=self.event)
        Transaction.objects.create(journal_entry=general, balance_delta=20, account=self.bank_account, event=self.event)

        response = self.client.get(reverse('accounts.views.show_event_detail',
                                           kwargs={'event_id': self.event.id}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/event_detail.html')
        self.assertEqual(response.context['event'], self.event)

    def test_show_event_detail_view_initial_no_transactions(self):
        '''
        A `GET` to the `show_event_detail` view with a valid `event_id` will
        return the respective `Event`. If no Transactions exist for this Event,
        all counters should return appropriately.
        '''
        response = self.client.get(reverse('accounts.views.show_event_detail',
                                           kwargs={'event_id': self.event.id}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/event_detail.html')
        self.assertEqual(response.context['event'], self.event)
        self.assertEqual(response.context['debit_total'], 0)
        self.assertEqual(response.context['credit_total'], 0)
        self.assertEqual(response.context['net_change'], 0)

    def test_show_event_detail_view_initial_only_credits(self):
        '''
        A `GET` to the `show_event_detail` view with a valid `event_id` will
        also return the correct counters for `net_change`, `debit_total` and
        `credit_total` when only credits are present.
        '''
        general = create_entry(datetime.date.today(), 'general entry')
        Transaction.objects.create(journal_entry=general, balance_delta=20, account=self.bank_account, event=self.event)
        Transaction.objects.create(journal_entry=general, balance_delta=20, account=self.bank_account, event=self.event)

        response = self.client.get(reverse('accounts.views.show_event_detail',
                                           kwargs={'event_id': self.event.id}))
        self.assertEqual(response.context['debit_total'], 0)
        self.assertEqual(response.context['credit_total'], 40)
        self.assertEqual(response.context['net_change'], 40)

    def test_show_event_detail_view_initial_only_debits(self):
        '''
        A `GET` to the `show_event_detail` view with a valid `event_id` will
        also return the correct counters for `net_change`,`debit_total` and
        `credit_total` when only debits are present.
        '''
        general = create_entry(datetime.date.today(), 'general entry')
        Transaction.objects.create(journal_entry=general, balance_delta=-20, account=self.bank_account, event=self.event)
        Transaction.objects.create(journal_entry=general, balance_delta=-20, account=self.bank_account, event=self.event)

        response = self.client.get(reverse('accounts.views.show_event_detail',
                                           kwargs={'event_id': self.event.id}))
        self.assertEqual(response.context['debit_total'], -40)
        self.assertEqual(response.context['credit_total'], 0)
        self.assertEqual(response.context['net_change'], -40)

    def test_show_event_detail_view_initial_debit_and_credit(self):
        '''
        A `GET` to the `show_event_detail` view with a valid `event_id` will
        also return the correct counters for `net_change`, `debit_total` and
        `credit_total` when credits and debits are present.
        '''
        general = create_entry(datetime.date.today(), 'general entry')
        Transaction.objects.create(journal_entry=general, balance_delta=20, account=self.bank_account, event=self.event)
        Transaction.objects.create(journal_entry=general, balance_delta=-20, account=self.bank_account, event=self.event)

        response = self.client.get(reverse('accounts.views.show_event_detail',
                                           kwargs={'event_id': self.event.id}))
        self.assertEqual(response.context['debit_total'], -20)
        self.assertEqual(response.context['credit_total'], 20)
        self.assertEqual(response.context['net_change'], 0)

    def test_show_event_detail_view_fail(self):
        '''
        A `GET` to the `show_event_detail` view with an invalid `event_id` will
        return a 404.
        '''
        response = self.client.get(reverse('accounts.views.show_event_detail',
                                           kwargs={'event_id': 90000001}))
        self.assertEqual(response.status_code, 404)


class JournalEntryViewTests(TestCase):
    '''
    Test JournalEntry add and detail views
    '''
    def setUp(self):
        '''
        JournalEntries require two accounts
        '''
        self.asset_header = create_header('asset', cat_type=1)
        self.expense_header = create_header('expense', cat_type=6)
        self.asset_account = create_account('asset', self.asset_header, 0, 1)
        self.expense_account = create_account('expense', self.expense_header, 0, 6)
        self.event = Event.objects.create(name='test event 1', date=datetime.date.today(),
                                          number='1', city='min', state='VA')

    def test_journal_add_view_initial(self):
        '''
        A `GET` to the `add_journal_entry` view should display JournalEntry Form
        and Transaction Formset.
        '''
        response = self.client.get(reverse('accounts.views.add_journal_entry'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/entry_add.html')
        self.failUnless(isinstance(response.context['entry_form'], JournalEntryForm))
        self.assertEqual(response.context['journal_type'], 'GJ')
        self.failUnless(isinstance(response.context['transaction_formset'], TransactionFormSet))

    def test_add_journal_entry_view_success(self):
        '''
        A `POST` to the `add_journal_entry` view with valid data will create a
        JournalEntry and it's respective Transactions.
        '''
        response = self.client.post(reverse('accounts.views.add_journal_entry'),
                                    data={'entry-date': datetime.date.today(),
                                          'entry-memo': 'test GJ entry',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 0,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': '',
                                          'transaction-0-journal_entry': '',
                                          'transaction-0-account': self.asset_account.id,
                                          'transaction-0-debit': 5,
                                          'transaction-0-event': self.event.id,
                                          'transaction-1-id': '',
                                          'transaction-1-journal_entry': '',
                                          'transaction-1-account': self.expense_account.id,
                                          'transaction-1-credit': 5,
                                          'subbtn': 'Submit'})
        self.assertRedirects(response, reverse('accounts.views.show_journal_entry',
                                               kwargs={'journal_id': 1}))
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertEqual(Account.objects.all()[0].balance, -5)
        self.assertEqual(Account.objects.all()[1].balance, 5)

    def test_add_journal_entry_view_fail_entry(self):
        '''
        A `POST` to the `add_journal_entry` view with invalid entry data will not
        create a JournalEntry or Transactions and displays an error message.
        '''
        response = self.client.post(reverse('accounts.views.add_journal_entry'),
                                    data={'entry-date': '',
                                          'entry-memo': '',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 0,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': '',
                                          'transaction-0-journal_entry': '',
                                          'transaction-0-account': self.asset_account.id,
                                          'transaction-0-debit': 5,
                                          'transaction-0-event': self.event.id,
                                          'transaction-1-id': '',
                                          'transaction-1-journal_entry': '',
                                          'transaction-1-account': self.expense_account.id,
                                          'transaction-1-credit': 5,
                                          'subbtn': 'Submit'})
        self.assertEqual(response.status_code, 200)
        self.failIf(response.context['entry_form'].is_valid())
        self.assertFormError(response, 'entry_form', 'date', 'This field is required.')
        self.assertFormError(response, 'entry_form', 'memo', 'This field is required.')
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(Account.objects.get(name='asset').balance, 0)
        self.assertEqual(Account.objects.get(name='expense').balance, 0)

    def test_add_journal_entry_view_fail_out_of_balance(self):
        '''
        A `POST` to the `add_journal_entry` view with invalid Transaction data
        should not create a JournalEntry or Transactions and displays an error
        message.
        '''
        response = self.client.post(reverse('accounts.views.add_journal_entry'),
                                    data={'entry-date': '4/20/2013',
                                          'entry-memo': 'test GJ entry',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 0,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': '',
                                          'transaction-0-journal_entry': '',
                                          'transaction-0-detail': 'test detail',
                                          'transaction-0-credit': 18,
                                          'transaction-0-account': self.asset_account.id,
                                          'transaction-1-id': '',
                                          'transaction-1-journal_entry': '',
                                          'transaction-1-detail': 'test detail',
                                          'transaction-1-debit': 15,
                                          'transaction-1-account': self.expense_account.id,
                                          'subbtn': 'Submit',
                                          })
        self.assertEqual(response.status_code, 200)
        self.failIf(response.context['transaction_formset'].is_valid())
        self.assertEqual(response.context['transaction_formset'].non_form_errors()[0],
                         'Transactions are out of balance.')
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(Account.objects.get(name='asset').balance, 0)
        self.assertEqual(Account.objects.get(name='expense').balance, 0)

    def test_add_journal_entry_view_fail_transactions_empty(self):
        '''
        A `POST` to the `add_journal_entry` view with no Transaction data
        should not create a JournalEntry or Transactions and displays an error
        message.
        refs #88: Empty Entries are Allowed to be Submit
        '''
        response = self.client.post(reverse('accounts.views.add_journal_entry'),
                                    data={'entry-date': '4/20/2013',
                                          'entry-memo': 'test GJ entry',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 0,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': '',
                                          'transaction-0-journal_entry': '',
                                          'transaction-0-detail': 'test detail',
                                          'transaction-0-credit': '',
                                          'transaction-0-account': '',
                                          'transaction-1-id': '',
                                          'transaction-1-journal_entry': '',
                                          'transaction-1-detail': '',
                                          'transaction-1-debit': '',
                                          'transaction-1-account': '',
                                          'subbtn': 'Submit',
                                          })
        self.assertEqual(response.status_code, 200)
        self.failIf(response.context['transaction_formset'].is_valid())
        self.assertEqual(response.context['transaction_formset'].forms[0].errors['account'],
                         ['This field is required.'])
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(Account.objects.get(name='asset').balance, 0)
        self.assertEqual(Account.objects.get(name='expense').balance, 0)

    def test_add_journal_entry_view_add_another(self):
        '''
        A `POST` to the `add_journal_entry` view with valid data and a submit
        value of 'Submit & Add More' will create a JournalEntry and it's
        respective Transactions, redirecting back to the Add page.
        '''
        response = self.client.post(reverse('accounts.views.add_journal_entry'),
                                    data={'entry-date': datetime.date.today(),
                                          'entry-memo': 'test GJ entry',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 0,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': '',
                                          'transaction-0-journal_entry': '',
                                          'transaction-0-account': self.asset_account.id,
                                          'transaction-0-debit': 5,
                                          'transaction-0-event': self.event.id,
                                          'transaction-1-id': '',
                                          'transaction-1-journal_entry': '',
                                          'transaction-1-account': self.expense_account.id,
                                          'transaction-1-credit': 5,
                                          'subbtn': 'Submit & Add More'})
        self.assertRedirects(response, reverse('accounts.views.add_journal_entry'))
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertEqual(Account.objects.all()[0].balance, -5)
        self.assertEqual(Account.objects.all()[1].balance, 5)

    def test_add_journal_entry_view_delete(self):
        '''
        A `POST` to the `add_journal_entry` view with a `journal_id` and a submit
        value of 'Delete' will delete the JournalEntry and all related Transactions,
        refunding the respective Accounts.
        '''
        entry = create_entry(datetime.date.today(), 'test memo')
        create_transaction(entry, self.asset_account, 50)
        create_transaction(entry, self.expense_account, -50)

        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertEqual(Account.objects.get(name='asset').balance, 50)
        self.assertEqual(Account.objects.get(name='expense').balance, -50)

        response = self.client.post(reverse('accounts.views.add_journal_entry',
                                            kwargs={'journal_id': entry.id}),
                                    data={'delete': 'Delete'})

        self.assertRedirects(response, reverse('accounts.views.journal_ledger'))
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(Account.objects.get(name='asset').balance, 0)
        self.assertEqual(Account.objects.get(name='expense').balance, 0)

    def test_add_journal_entry_view_delete_fail(self):
        '''
        A `POST` to the `add_journal_entry` view with an invalid `journal_id`
        will return a 404.
        '''
        self.assertEqual(JournalEntry.objects.count(), 0)
        response = self.client.post(reverse('accounts.views.add_journal_entry',
                                            kwargs={'journal_id': 9001}),
                                    data={'delete': 'Delete'})
        self.assertEqual(response.status_code, 404)

    def test_add_journal_entry_view_fiscal_year(self):
        '''
        A `POST` to the ``add_journal_entry`` view with a ``date`` on or after
        the start of the current ``FiscalYear`` will create a JournalEntry
        and Transactions.
        If there is only one FiscalYear, the ``period`` amount of months before
        the ``end_month`` is used.
        '''
        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        response = self.client.post(reverse('accounts.views.add_journal_entry'),
                                    data={'entry-date': datetime.date(2011, 1, 1),
                                          'entry-memo': 'test GJ entry',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 0,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': '',
                                          'transaction-0-journal_entry': '',
                                          'transaction-0-account': self.asset_account.id,
                                          'transaction-0-debit': 5,
                                          'transaction-0-event': self.event.id,
                                          'transaction-1-id': '',
                                          'transaction-1-journal_entry': '',
                                          'transaction-1-account': self.expense_account.id,
                                          'transaction-1-credit': 5,
                                          'subbtn': 'Submit'})
        self.assertRedirects(response, reverse('accounts.views.show_journal_entry',
                                               kwargs={'journal_id': 1}))
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertEqual(Account.objects.all()[0].balance, -5)
        self.assertEqual(Account.objects.all()[1].balance, 5)

    def test_add_journal_entry_view_fail_fiscal_year(self):
        '''
        A `POST` to the ``add_journal_entry`` view with a ``date`` before
        the start of the current ``FiscalYear`` will not create a JournalEntry
        or Transactions and displays and error message.
        If there is only one FiscalYear, the ``period`` amount of months before
        the ``end_month`` is used.
        '''
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        response = self.client.post(reverse('accounts.views.add_journal_entry'),
                                    data={'entry-date': datetime.date(2011, 1, 1),
                                          'entry-memo': 'test GJ entry',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 0,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': '',
                                          'transaction-0-journal_entry': '',
                                          'transaction-0-account': self.asset_account.id,
                                          'transaction-0-debit': 5,
                                          'transaction-0-event': self.event.id,
                                          'transaction-1-id': '',
                                          'transaction-1-journal_entry': '',
                                          'transaction-1-account': self.expense_account.id,
                                          'transaction-1-credit': 5,
                                          'subbtn': 'Submit'})
        self.assertFalse(response.context['entry_form'].is_valid())
        self.assertFormError(response, 'entry_form', 'date',
                'The date must be in the current Fiscal Year.')
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(Account.objects.get(name='asset').balance, 0)
        self.assertEqual(Account.objects.get(name='expense').balance, 0)

    def test_add_journal_entry_view_two_fiscal_year(self):
        '''
        A `POST` to the ``add_journal_entry`` view with a ``date`` on or after
        the start of the current ``FiscalYear`` will create a JournalEntry
        and Transactions.
        If there is are multiple FiscalYear, the ``date`` cannot be before the
        ``end_month`` of the Second to Latest FiscalYear.
        '''
        FiscalYear.objects.create(year=2010, end_month=12, period=12)
        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        response = self.client.post(reverse('accounts.views.add_journal_entry'),
                                    data={'entry-date': datetime.date(2011, 1, 1),
                                          'entry-memo': 'test GJ entry',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 0,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': '',
                                          'transaction-0-journal_entry': '',
                                          'transaction-0-account': self.asset_account.id,
                                          'transaction-0-debit': 5,
                                          'transaction-0-event': self.event.id,
                                          'transaction-1-id': '',
                                          'transaction-1-journal_entry': '',
                                          'transaction-1-account': self.expense_account.id,
                                          'transaction-1-credit': 5,
                                          'subbtn': 'Submit'})
        self.assertRedirects(response, reverse('accounts.views.show_journal_entry',
                                               kwargs={'journal_id': 1}))
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertEqual(Account.objects.all()[0].balance, -5)
        self.assertEqual(Account.objects.all()[1].balance, 5)

    def test_add_journal_entry_view_fail_two_fiscal_year(self):
        '''
        A `POST` to the ``add_journal_entry`` view with a ``date`` before
        the start of the current ``FiscalYear`` will not create a JournalEntry
        or Transactions and displays and error message.
        If there is are multiple FiscalYear, the ``date`` cannot be before the
        ``end_month`` of the Second to Latest FiscalYear.
        '''
        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        response = self.client.post(reverse('accounts.views.add_journal_entry'),
                                    data={'entry-date': datetime.date(2011, 12, 31),
                                          'entry-memo': 'test GJ entry',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 0,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': '',
                                          'transaction-0-journal_entry': '',
                                          'transaction-0-account': self.asset_account.id,
                                          'transaction-0-debit': 5,
                                          'transaction-0-event': self.event.id,
                                          'transaction-1-id': '',
                                          'transaction-1-journal_entry': '',
                                          'transaction-1-account': self.expense_account.id,
                                          'transaction-1-credit': 5,
                                          'subbtn': 'Submit'})
        self.assertFalse(response.context['entry_form'].is_valid())
        self.assertFormError(response, 'entry_form', 'date',
                'The date must be in the current Fiscal Year.')
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(Account.objects.get(name='asset').balance, 0)
        self.assertEqual(Account.objects.get(name='expense').balance, 0)

    def test_add_journal_entry_view_edit_no_fiscal_year(self):
        '''
        A `GET` to the `add_journal_entry` view with a `journal_id` will return
        a JournalEntryForm and TransactionFormSet with the specified JournalEntry
        instance if there is no current FiscalYear.
        '''
        self.test_add_journal_entry_view_success()
        entry = JournalEntry.objects.all()[0]
        response = self.client.get(reverse('accounts.views.add_journal_entry',
                                           kwargs={'journal_id': JournalEntry.objects.all()[0].id}))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/entry_add.html')
        self.failUnless(isinstance(response.context['entry_form'], JournalEntryForm))
        self.failUnless(isinstance(response.context['transaction_formset'], TransactionFormSet))
        self.assertEqual(response.context['entry_form'].instance, entry)
        self.assertEqual(response.context['transaction_formset'].forms[0].instance,
                         entry.transaction_set.all()[0])
        self.assertEqual(response.context['transaction_formset'].forms[1].instance,
                         entry.transaction_set.all()[1])
        self.assertEqual(response.context['transaction_formset'].forms[0].initial['debit'], 5)
        self.assertEqual(response.context['transaction_formset'].forms[1].initial['credit'], 5)

    def test_add_journal_entry_view_edit_in_fiscal_year(self):
        '''
        A `GET` to the `add_journal_entry` view with a `journal_id` will return
        a JournalEntryForm and TransactionFormSet with the specified JournalEntry
        instance if the entry is in the current Fiscal Year
        '''
        today = datetime.date.today()
        FiscalYear.objects.create(year=today.year, end_month=12, period=12)
        self.test_add_journal_entry_view_success()
        entry = JournalEntry.objects.all()[0]
        response = self.client.get(reverse('accounts.views.add_journal_entry',
                                           kwargs={'journal_id': entry.id}))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/entry_add.html')

    def test_add_journal_entry_view_edit_out_of_fiscal_year(self):
        '''
        A `GET` to the `add_journal_entry` view with a `journal_id` will return
        a 404 Error if the entry is before the current Fiscal Year.
        '''
        self.test_add_journal_entry_view_success()
        today = datetime.date.today()
        FiscalYear.objects.create(year=today.year + 2, end_month=12, period=12)
        entry = JournalEntry.objects.all()[0]
        response = self.client.get(reverse('accounts.views.add_journal_entry',
                                           kwargs={'journal_id': entry.id}))

        self.assertEqual(response.status_code, 404)

    def test_add_journal_entry_view_edit_account_success(self):
        '''
        A `POST` to the `add_journal_entry` view with a `journal_id` should modify
        the JournalEntry and it's Transactions with the POSTed data and redirect
        to the Entry's detail page.
        '''
        self.test_add_journal_entry_view_success()
        response = self.client.post(reverse('accounts.views.add_journal_entry',
                                           kwargs={'journal_id': JournalEntry.objects.all()[0].id}),
                                    data={'entry-date': '5/1/11',
                                          'entry-memo': 'new memo!',
                                          'transaction-TOTAL_FORMS': 22,
                                          'transaction-INITIAL_FORMS': 2,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': 1,
                                          'transaction-0-journal_entry': 1,
                                          'transaction-0-account': self.expense_account.id,
                                          'transaction-0-debit': 5,
                                          'transaction-0-detail': 'debit',
                                          'transaction-0-event': self.event.id,
                                          'transaction-1-id': 2,
                                          'transaction-1-journal_entry': 1,
                                          'transaction-1-account': self.asset_account.id,
                                          'transaction-1-credit': 5,
                                          'transaction-1-detail': 'credit',
                                          'subbtn': 'Submit'})
        self.assertRedirects(response, reverse('accounts.views.show_journal_entry', kwargs={'journal_id': JournalEntry.objects.all()[0].id}))
        entry = JournalEntry.objects.all()[0]
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertEqual(entry.date, datetime.date(2011, 5, 1))
        self.assertEqual(entry.memo, 'new memo!')
        self.assertEqual(Account.objects.get(name='asset').balance, 5)
        self.assertEqual(Account.objects.get(name='expense').balance, -5)

    def test_add_journal_entry_view_edit_delta_success(self):
        '''
        A `POST` to the `add_journal_entry` view with a `journal_id` should modify
        the JournalEntry and it's Transactions with the POSTed data and redirect
        to the Entry's detail page.
        '''
        self.test_add_journal_entry_view_success()
        response = self.client.post(reverse('accounts.views.add_journal_entry',
                                           kwargs={'journal_id': JournalEntry.objects.all()[0].id}),
                                    data={'entry-date': '5/1/11',
                                          'entry-memo': 'new memo!',
                                          'transaction-TOTAL_FORMS': 22,
                                          'transaction-INITIAL_FORMS': 2,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': 1,
                                          'transaction-0-journal_entry': 1,
                                          'transaction-0-account': self.asset_account.id,
                                          'transaction-0-credit': 8,
                                          'transaction-0-detail': 'debit',
                                          'transaction-0-event': self.event.id,
                                          'transaction-1-id': 2,
                                          'transaction-1-journal_entry': 1,
                                          'transaction-1-account': self.expense_account.id,
                                          'transaction-1-debit': 8,
                                          'transaction-1-detail': 'credit',
                                          'subbtn': 'Submit'})
        self.assertRedirects(response, reverse('accounts.views.show_journal_entry', kwargs={'journal_id': JournalEntry.objects.all()[0].id}))
        entry = JournalEntry.objects.all()[0]
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertEqual(entry.date, datetime.date(2011, 5, 1))
        self.assertEqual(entry.memo, 'new memo!')
        self.assertEqual(Account.objects.get(name='asset').balance, 8)
        self.assertEqual(Account.objects.get(name='expense').balance, -8)

    def test_add_journal_entry_view_edit_account_and_delta_success(self):
        '''
        A `POST` to the `add_journal_entry` view with a `journal_id` should modify
        the JournalEntry and it's Transactions with the POSTed data and redirect
        to the Entry's detail page.
        '''
        self.test_add_journal_entry_view_success()
        response = self.client.post(reverse('accounts.views.add_journal_entry',
                                           kwargs={'journal_id': JournalEntry.objects.all()[0].id}),
                                    data={'entry-date': '5/1/11',
                                          'entry-memo': 'new memo!',
                                          'transaction-TOTAL_FORMS': 22,
                                          'transaction-INITIAL_FORMS': 2,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': 1,
                                          'transaction-0-journal_entry': 1,
                                          'transaction-0-account': self.expense_account.id,
                                          'transaction-0-debit': 8,
                                          'transaction-0-detail': 'debit',
                                          'transaction-1-id': 2,
                                          'transaction-1-journal_entry': 1,
                                          'transaction-1-account': self.asset_account.id,
                                          'transaction-1-credit': 8,
                                          'transaction-1-detail': 'credit',
                                          'transaction-1-event': self.event.id,
                                          'subbtn': 'Submit'})
        self.assertRedirects(response, reverse('accounts.views.show_journal_entry', kwargs={'journal_id': JournalEntry.objects.all()[0].id}))
        entry = JournalEntry.objects.all()[0]
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertEqual(entry.date, datetime.date(2011, 5, 1))
        self.assertEqual(entry.memo, 'new memo!')
        self.assertEqual(Account.objects.get(name='asset').balance, 8)
        self.assertEqual(Account.objects.get(name='expense').balance, -8)
        self.assertEqual(Transaction.objects.get(account=self.expense_account).event, None)
        self.assertEqual(Transaction.objects.get(account=self.asset_account).event, self.event)

    def test_add_journal_entry_view_edit_new_transactions_success(self):
        '''
        A `POST` to the `add_journal_entry` view with a `journal_id` should modify
        the JournalEntry and it's Transactions with the POSTed data and redirect
        to the Entry's detail page.
        '''
        self.test_add_journal_entry_view_success()
        response = self.client.post(reverse('accounts.views.add_journal_entry',
                                           kwargs={'journal_id': JournalEntry.objects.all()[0].id}),
                                    data={'entry-date': '5/1/11',
                                          'entry-memo': 'new memo!',
                                          'transaction-TOTAL_FORMS': 22,
                                          'transaction-INITIAL_FORMS': 2,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': 1,
                                          'transaction-0-journal_entry': 1,
                                          'transaction-0-account': self.asset_account.id,
                                          'transaction-0-debit': 8,
                                          'transaction-0-detail': 'debit',
                                          'transaction-0-event': self.event.id,
                                          'transaction-1-id': 2,
                                          'transaction-1-journal_entry': 1,
                                          'transaction-1-account': self.expense_account.id,
                                          'transaction-1-credit': 5,
                                          'transaction-1-detail': 'credit',
                                          'transaction-2-id': '',
                                          'transaction-2-journal_entry': 1,
                                          'transaction-2-account': self.asset_account.id,
                                          'transaction-2-credit': 3,
                                          'subbtn': 'Submit'})
        self.assertRedirects(response, reverse('accounts.views.show_journal_entry', kwargs={'journal_id': JournalEntry.objects.all()[0].id}))
        entry = JournalEntry.objects.all()[0]
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 3)
        self.assertEqual(entry.date, datetime.date(2011, 5, 1))
        self.assertEqual(entry.memo, 'new memo!')
        self.assertEqual(Account.objects.get(name='asset').balance, -5)
        self.assertEqual(Account.objects.get(name='expense').balance, 5)

    def test_add_journal_entry_view_edit_account_and_balance_change_new_transactions_success(self):
        '''
        A `POST` to the `add_journal_entry` view with a `journal_id` should modify
        the JournalEntry and it's Transactions with the POSTed data and redirect
        to the Entry's detail page.
        '''
        self.test_add_journal_entry_view_success()
        response = self.client.post(reverse('accounts.views.add_journal_entry',
                                           kwargs={'journal_id': JournalEntry.objects.all()[0].id}),
                                    data={'entry-date': '5/1/11',
                                          'entry-memo': 'new memo!',
                                          'transaction-TOTAL_FORMS': 22,
                                          'transaction-INITIAL_FORMS': 2,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': 1,
                                          'transaction-0-journal_entry': 1,
                                          'transaction-0-account': self.expense_account.id,
                                          'transaction-0-credit': 8,
                                          'transaction-0-detail': 'debit',
                                          'transaction-0-event': self.event.id,
                                          'transaction-1-id': 2,
                                          'transaction-1-journal_entry': 1,
                                          'transaction-1-account': self.asset_account.id,
                                          'transaction-1-credit': 10,
                                          'transaction-1-detail': 'credit',
                                          'transaction-2-id': '',
                                          'transaction-2-journal_entry': 1,
                                          'transaction-2-account': self.expense_account.id,
                                          'transaction-2-debit': 18,
                                          'subbtn': 'Submit'})
        self.assertRedirects(response, reverse('accounts.views.show_journal_entry', kwargs={'journal_id': JournalEntry.objects.all()[0].id}))
        entry = JournalEntry.objects.all()[0]
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 3)
        self.assertEqual(entry.date, datetime.date(2011, 5, 1))
        self.assertEqual(entry.memo, 'new memo!')
        self.assertEqual(Account.objects.get(name='asset').balance, 10)
        self.assertEqual(Account.objects.get(name='expense').balance, -10)

    def test_add_journal_entry_view_post_fail(self):
        '''
        A `POST` to the `add_journal_entry` view with no 'submit' value will
        return a 404.
        '''
        response = self.client.post(reverse('accounts.views.add_journal_entry',
                                            kwargs={'journal_id': 9001}))
        self.assertEqual(response.status_code, 404)

    def test_show_journal_entry_view(self):
        '''
        A `GET` to the `show_journal_entry` view with a journal_id will retrieve
        the JournalEntry, it's Transactions, debit and credit totals and whether
        it has been updated.
        '''
        entry = create_entry(datetime.date.today(), 'test memo')
        create_transaction(entry, self.asset_account, 50)
        create_transaction(entry, self.expense_account, -50)

        response = self.client.get(reverse('accounts.views.show_journal_entry',
                                           kwargs={'journal_id': 1}))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/entry_detail.html')
        self.assertEqual(response.context['journal_entry'], JournalEntry.objects.all()[0])
        self.assertItemsEqual(response.context['transactions'], Transaction.objects.all())
        self.assertEqual(response.context['updated'], False)
        self.assertEqual(response.context['credit_total'], 50)
        self.assertEqual(response.context['debit_total'], -50)

        entry.created_at = datetime.datetime(datetime.date.today().year - 20, 1, 1, 1, 1, 1, tzinfo=utc)
        entry.save()
        response = self.client.get(reverse('accounts.views.show_journal_entry',
                                           kwargs={'journal_id': 1}))
        self.assertEqual(response.context['updated'], True)

    def test_show_journal_entry_view_fail(self):
        '''
        A `GET` to the `show_journal_entry` view with an invalid journal_id will
        return a 404.
        '''
        response = self.client.get(reverse('accounts.views.show_journal_entry',
                                           kwargs={'journal_id': '2343'}))
        self.assertEqual(response.status_code, 404)


class TransferEntryViewTests(TestCase):
    '''
    Test TransferEntry add view
    '''
    def setUp(self):
        self.asset_header = create_header('asset', cat_type=1)
        self.expense_header = create_header('expense', cat_type=6)
        self.asset_account = create_account('asset', self.asset_header, 0, 1)
        self.expense_account = create_account('expense', self.expense_header, 0, 6)

    def test_transfer_add_view_initial(self):
        '''
        A `GET` to the `add_transfer_entry` view should display a JournalEntry Form
        and Transfer Formset.
        '''
        response = self.client.get(reverse('accounts.views.add_transfer_entry'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/entry_add.html')
        self.failUnless(isinstance(response.context['entry_form'], JournalEntryForm))
        self.assertNotIn('journal_type', response.context)
        self.failUnless(isinstance(response.context['transaction_formset'], TransferFormSet))

    def test_transfer_add_view_success(self):
        '''
        A `POST` to the `add_transfer_entry` view should create a JournalEntry
        and related Transactions, redirecting to the Entry Detail Page.
        '''
        response = self.client.post(reverse('accounts.views.add_transfer_entry'),
                                    data={'entry-date': datetime.date.today(),
                                          'entry-memo': 'test transfer entry',
                                          'transfer-TOTAL_FORMS': 20,
                                          'transfer-INITIAL_FORMS': 0,
                                          'transfer-MAX_NUM_FORMS': '',
                                          'transfer-0-id': '',
                                          'transfer-0-journal_entry': '',
                                          'transfer-0-source': 1,
                                          'transfer-0-destination': 2,
                                          'transfer-0-amount': 15,
                                          'subbtn': 'Submit'})
        self.assertRedirects(response, reverse('accounts.views.show_journal_entry', kwargs={'journal_id': 1}))
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(Account.objects.all()[0].balance, -15)
        self.assertEqual(Account.objects.all()[1].balance, 15)

    def test_transfer_add_view_fail_entry(self):
        '''
        A `POST` to the `add_transfer_entry` view with invalid Entry data should
        not create a JournalEntry or Transactions and should return any errors.
        '''
        response = self.client.post(reverse('accounts.views.add_transfer_entry'),
                                    data={'entry-date': '',
                                          'entry-memo': '',
                                          'transfer-TOTAL_FORMS': 20,
                                          'transfer-INITIAL_FORMS': 0,
                                          'transfer-MAX_NUM_FORMS': '',
                                          'transfer-0-id': '',
                                          'transfer-0-journal_entry': '',
                                          'transfer-0-source': 1,
                                          'transfer-0-destination': 2,
                                          'transfer-0-amount': 15,
                                          'subbtn': 'Submit'})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'entry_form', 'date', 'This field is required.')
        self.assertFormError(response, 'entry_form', 'memo', 'This field is required.')
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(Account.objects.all()[0].balance, 0)
        self.assertEqual(Account.objects.all()[1].balance, 0)

    def test_transfer_add_view_fail_no_dest(self):
        '''
        A `POST` to the `add_transfer_entry` view with invalid Transaction data
        should not create a JournalEntry or Transactions and should return any
        errors.
        '''
        response = self.client.post(reverse('accounts.views.add_transfer_entry'),
                                    data={'entry-date': datetime.date.today(),
                                          'entry-memo': 'test transfer entry',
                                          'transfer-TOTAL_FORMS': 20,
                                          'transfer-INITIAL_FORMS': 0,
                                          'transfer-MAX_NUM_FORMS': '',
                                          'transfer-0-id': '',
                                          'transfer-0-journal_entry': '',
                                          'transfer-0-source': '1',
                                          'transfer-0-destination': '',
                                          'transfer-0-amount': '',
                                          'subbtn': 'Submit'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['transaction_formset'].forms[0].errors['amount'], ['This field is required.'])
        self.assertEqual(response.context['transaction_formset'].forms[0].errors['destination'], ['This field is required.'])
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(Account.objects.all()[0].balance, 0)
        self.assertEqual(Account.objects.all()[1].balance, 0)

    def test_transfer_add_view_fail_transactions_empty(self):
        '''
        A `POST` to the `add_transfer_entry` view with no Transaction data
        should not create a JournalEntry or Transactions and should return any
        errors.
        refs #88: Empty Entries are Allowed to be Submit
        '''
        response = self.client.post(reverse('accounts.views.add_transfer_entry'),
                                    data={'entry-date': datetime.date.today(),
                                          'entry-memo': 'test transfer entry',
                                          'transfer-TOTAL_FORMS': 20,
                                          'transfer-INITIAL_FORMS': 0,
                                          'transfer-MAX_NUM_FORMS': '',
                                          'transfer-0-id': '',
                                          'transfer-0-journal_entry': '',
                                          'transfer-0-source': '',
                                          'transfer-0-destination': '',
                                          'transfer-0-amount': '',
                                          'subbtn': 'Submit'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['transaction_formset'].forms[0].errors['amount'],
                         ['This field is required.'])
        self.assertEqual(response.context['transaction_formset'].forms[0].errors['destination'],
                         ['This field is required.'])
        self.assertEqual(response.context['transaction_formset'].forms[0].errors['source'],
                         ['This field is required.'])
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(Account.objects.all()[0].balance, 0)
        self.assertEqual(Account.objects.all()[1].balance, 0)


class BankEntryViewTests(TestCase):
    '''
    Test the BankSpendingEntry and BankReceivingEntry add and detail views
    '''
    def setUp(self):
        '''
        Bank Entries require a Bank Account(Assets) and a normal Account(assume Expense)
        '''
        self.asset_header = create_header('asset', cat_type=1)
        self.expense_header = create_header('expense', cat_type=6)
        self.bank_account = create_account('bank', self.asset_header, 0, 1, True)
        self.expense_account = create_account('expense', self.expense_header, 0, 6)

    def test_bank_receiving_add_view_initial(self):
        '''
        A `GET` to the `add_bank_entry` view with a `journal_type` of `CR`
        should display BankReceving Forms and Formsets.
        '''
        response = self.client.get(reverse('accounts.views.add_bank_entry', kwargs={'journal_type': 'CR'}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/entry_add.html')
        self.failUnless(isinstance(response.context['entry_form'], BankReceivingForm))
        self.assertEqual(response.context['journal_type'], 'CR')
        self.failUnless(isinstance(response.context['transaction_formset'], BankReceivingTransactionFormSet))

    def test_bank_receiving_add_view_success(self):
        '''
        A `POST` to the 'add_bank_entry' view with a `journal_type` of `CR`
        should create a new BankReceivingEntry and issue a redirect.
        '''
        response = self.client.post(reverse('accounts.views.add_bank_entry', kwargs={'journal_type': 'CR'}),
                                    data={'entry-account': self.bank_account.id,
                                          'entry-date': '2013-03-12',
                                          'entry-payor': 'test payor',
                                          'entry-amount': 20,
                                          'entry-memo': 'test memo',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 0,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': '',
                                          'transaction-0-bankspend_entry': '',
                                          'transaction-0-detail': 'test detail',
                                          'transaction-0-amount': 20,
                                          'transaction-0-account': self.expense_account.id,
                                          'subbtn': 'Submit',
                                          })

        self.assertRedirects(response, reverse('accounts.views.show_bank_entry',
                                               kwargs={'journal_type': 'CR', 'journal_id': 1}))
        self.assertEqual(BankReceivingEntry.objects.count(), 1)
        self.assertEqual(Account.objects.get(bank=True).balance, -20)
        self.assertEqual(Account.objects.get(bank=False).balance, 20)

    def test_bank_receiving_add_view_failure_entry(self):
        '''
        A `POST` to the `add_bank_entry` view with a journal type of `CR` with
        invalid entry data will not create a BankReceivingEntry and displays
        an error message.
        '''
        response = self.client.post(reverse('accounts.views.add_bank_entry', kwargs={'journal_type': 'CR'}),
                                    data={'entry-account': self.bank_account.id,
                                          'entry-date': '2013-03-12',
                                          'entry-payor': '',
                                          'entry-amount': 20,
                                          'entry-memo': 'test memo',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 0,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': '',
                                          'transaction-0-bankspend_entry': '',
                                          'transaction-0-detail': 'test detail',
                                          'transaction-0-amount': 20,
                                          'transaction-0-account': self.expense_account.id,
                                          'subbtn': 'Submit',
                                          })
        self.assertEqual(response.status_code, 200)
        self.failIf(response.context['entry_form'].is_valid())
        self.assertFormError(response, 'entry_form', 'payor', 'This field is required.')
        self.assertEqual(BankReceivingEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_bank_receiving_add_view_failure_transaction(self):
        '''
        A `POST` to the `add_bank_entry` view with a journal type of `CR` with
        invalid transaction data will not create a BankReceivingEntry and displays
        an error message.
        '''
        response = self.client.post(reverse('accounts.views.add_bank_entry', kwargs={'journal_type': 'CR'}),
                                    data={'entry-account': self.bank_account.id,
                                          'entry-date': '2013-03-12',
                                          'entry-payor': 'test payor',
                                          'entry-amount': 20,
                                          'entry-memo': 'test memo',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 0,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': '',
                                          'transaction-0-bankspend_entry': '',
                                          'transaction-0-detail': 'test detail',
                                          'transaction-0-amount': 18,
                                          'transaction-0-account': self.expense_account.id,
                                          'subbtn': 'Submit',
                                          })
        self.assertEqual(response.status_code, 200)
        self.failIf(response.context['transaction_formset'].is_valid())
        self.assertEqual(response.context['transaction_formset'].non_form_errors()[0],
                         'Transactions are out of balance.')
        self.assertEqual(BankReceivingEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_bank_receiving_add_view_add_another(self):
        '''
        A `POST` to the 'add_bank_entry' view with a `journal_type` of `CR` and
        submit value of `Submit & Add Another` should create a new BankReceivingEntry
        and issue redirect back to the Add page, initializing the entry form with
        last Entries bank_account.
        '''
        response = self.client.post(reverse('accounts.views.add_bank_entry', kwargs={'journal_type': 'CR'}),
                                    data={'entry-account': self.bank_account.id,
                                          'entry-date': '2013-03-12',
                                          'entry-payor': 'test payor',
                                          'entry-amount': 20,
                                          'entry-memo': 'test memo',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 0,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': '',
                                          'transaction-0-bankspend_entry': '',
                                          'transaction-0-detail': 'test detail',
                                          'transaction-0-amount': 20,
                                          'transaction-0-account': self.expense_account.id,
                                          'subbtn': 'Submit & Add More',
                                          })

        self.assertRedirects(response, reverse('accounts.views.add_bank_entry', kwargs={'journal_type': 'CR'}) + '?bank_account={0}'.format(self.bank_account.id))
        response = self.client.get(response._headers['location'][1])
        self.assertEqual(response.context['entry_form'].initial['account'], str(self.bank_account.id))
        self.assertEqual(BankReceivingEntry.objects.count(), 1)
        self.assertEqual(Account.objects.get(bank=True).balance, -20)
        self.assertEqual(Account.objects.get(bank=False).balance, 20)

    def test_bank_receiving_add_view_delete(self):
        '''
        A `POST` to the `add_bank_entry` view with a `journal_id` and
        `journal_type` of 'CR' will delete the BankReceivingEntry and all related
        Transactions, refunding the respective Accounts.
        '''
        self.test_bank_receiving_add_view_success()
        entry = BankReceivingEntry.objects.all()[0]

        self.assertEqual(BankReceivingEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertEqual(Account.objects.get(name='bank').balance, -20)
        self.assertEqual(Account.objects.get(name='expense').balance, 20)

        response = self.client.post(reverse('accounts.views.add_bank_entry',
                                            kwargs={'journal_id': entry.id,
                                                    'journal_type': 'CR'}),
                                    data={'delete': 'Delete'})

        self.assertRedirects(response, reverse('accounts.views.bank_register',
                                               kwargs={'account_slug': self.bank_account.slug}))
        self.assertEqual(BankReceivingEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(Account.objects.get(name='bank').balance, 0)
        self.assertEqual(Account.objects.get(name='expense').balance, 0)

    def test_bank_receiving_add_view_delete_fail(self):
        '''
        A `POST` to the `add_bank_entry` view with an invalid `journal_id` and
        `journal_type` of 'CR' will return a 404.
        '''
        self.assertEqual(BankReceivingEntry.objects.count(), 0)
        response = self.client.post(reverse('accounts.views.add_bank_entry',
                                            kwargs={'journal_id': 9001,
                                                    'journal_type': 'CR'}),
                                    data={'delete': 'Delete'})
        self.assertEqual(response.status_code, 404)

    def test_bank_receiving_add_view_edit(self):
        '''
        A `GET` to the `add_bank_entry` view with a `journal_type` of `CR` and
        a `journal_id` should display BankReceiving Forms and Formsets using an
        instance of the BankReceivingEntry with id `journal_id` if there is
        no current FiscalYear.
        '''
        self.test_bank_receiving_add_view_success()
        entry = BankReceivingEntry.objects.all()[0]
        response = self.client.get(reverse('accounts.views.add_bank_entry',
                                           kwargs={'journal_type': 'CR',
                                                   'journal_id': entry.id}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/entry_add.html')
        self.failUnless(isinstance(response.context['entry_form'], BankReceivingForm))
        self.failUnless(isinstance(response.context['transaction_formset'], BankReceivingTransactionFormSet))
        self.assertEqual(response.context['entry_form'].instance, entry)
        self.assertEqual(response.context['entry_form'].initial['amount'],
                         -1 * entry.main_transaction.balance_delta)
        self.assertEqual(response.context['entry_form'].initial['account'],
                         entry.main_transaction.account)
        self.assertEqual(response.context['transaction_formset'].forms[0].instance,
                         entry.transaction_set.all()[0])
        self.assertEqual(response.context['transaction_formset'].forms[0].initial['amount'],
                         entry.transaction_set.all()[0].balance_delta)

    def test_bank_receiving_add_view_edit_success(self):
        '''
        A `POST` to the 'add_bank_entry' view with a `journal_type` of `CR` with
        a `journal_id` should edit the respective BankReceivingEntry and issue a
        redirect.
        '''
        self.test_bank_receiving_add_view_success()
        new_bank_account = create_account('2nd bank', self.asset_header, 0, 1, True)
        new_expense_account = create_account('2nd expense', self.expense_header, 0, 6)
        response = self.client.post(reverse('accounts.views.add_bank_entry', kwargs={'journal_type': 'CR',
                                                                                     'journal_id': 1}),
                                    data={'entry-account': new_bank_account.id,
                                          'entry-date': '4/20/1999',
                                          'entry-payor': 'new payor',
                                          'entry-amount': 20,
                                          'entry-memo': 'new memo',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 1,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': 2,
                                          'transaction-0-bankreceive_entry': 1,
                                          'transaction-0-detail': 'test detail',
                                          'transaction-0-amount': 15,
                                          'transaction-0-account': new_expense_account.id,
                                          'transaction-1-id': '',
                                          'transaction-1-bankreceive_entry': 1,
                                          'transaction-1-detail': 'test detail 2',
                                          'transaction-1-amount': 5,
                                          'transaction-1-account': self.expense_account.id,
                                          'subbtn': 'Submit',
                                          })
        self.assertRedirects(response, reverse('accounts.views.show_bank_entry',
                                               kwargs={'journal_type': 'CR', 'journal_id': 1}))
        self.assertEqual(BankReceivingEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 3)
        entry = BankReceivingEntry.objects.all()[0]
        self.assertEqual(entry.date, datetime.date(1999, 4, 20))
        self.assertEqual(entry.memo, 'new memo')
        self.assertEqual(entry.payor, 'new payor')
        self.assertEqual(entry.main_transaction.balance_delta, -20)
        bank_account = Account.objects.get(name='bank')
        expense_account = Account.objects.get(name='expense')
        new_bank_account = Account.objects.get(name='2nd bank')
        new_expense_account = Account.objects.get(name='2nd expense')
        self.assertEqual(bank_account.balance, 0)
        self.assertEqual(expense_account.balance, 5)
        self.assertEqual(new_bank_account.balance, -20)
        self.assertEqual(new_expense_account.balance, 15)
        self.assertEqual(new_bank_account, Transaction.objects.all()[0].account)
        self.assertEqual(new_expense_account, Transaction.objects.all()[1].account)
        self.assertEqual(self.expense_account, Transaction.objects.all()[2].account)

    def test_bank_receiving_add_view_edit_in_fiscal_year(self):
        '''
        A `GET` to the `add_bank_entry` view with a `journal_type` of `CR` and
        a `journal_id` should display BankReceiving Forms and Formsets using an
        instance of the BankReceivingEntry with id `journal_id` if the `date`
        is in the current FiscalYear.
        '''
        FiscalYear.objects.create(year=2013, end_month=12, period=12)
        self.test_bank_receiving_add_view_success()
        entry = BankReceivingEntry.objects.all()[0]
        response = self.client.get(reverse('accounts.views.add_bank_entry',
                                           kwargs={'journal_type': 'CR',
                                                   'journal_id': entry.id}))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/entry_add.html')

    def test_bank_receiving_add_view_edit_out_of_fiscal_year(self):
        '''
        A `GET` to the `add_journal_entry` view with a `journal_id` will return
        a 404 Error if the entry is before the current Fiscal Year.
        '''
        self.test_bank_receiving_add_view_success()
        FiscalYear.objects.create(year=2015, end_month=12, period=12)
        entry = BankReceivingEntry.objects.all()[0]
        response = self.client.get(reverse('accounts.views.add_bank_entry',
                                           kwargs={'journal_type': 'CR',
                                                   'journal_id': entry.id}))

        self.assertEqual(response.status_code, 404)

    def test_bank_receiving_add_view_fiscal_year(self):
        '''
        A `POST` to the ``add_bank_entry`` view with a ``journal_type`` of
        ``CR`` and a ``date`` on or after the start of the current
        ``FiscalYear`` will create a BankReceivingEntry and Transactions.
        If there is only one FiscalYear, the ``period`` amount of months before
        the ``end_month`` is used.
        '''
        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        response = self.client.post(reverse('accounts.views.add_bank_entry', kwargs={'journal_type': 'CR'}),
                                    data={'entry-account': self.bank_account.id,
                                          'entry-date': '2013-03-12',
                                          'entry-payor': 'test payor',
                                          'entry-amount': 20,
                                          'entry-memo': 'test memo',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 0,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': '',
                                          'transaction-0-bankspend_entry': '',
                                          'transaction-0-detail': 'test detail',
                                          'transaction-0-amount': 20,
                                          'transaction-0-account': self.expense_account.id,
                                          'subbtn': 'Submit',
                                          })
        self.assertRedirects(response, reverse('accounts.views.show_bank_entry',
                                               kwargs={'journal_type': 'CR', 'journal_id': 1}))
        self.assertEqual(BankReceivingEntry.objects.count(), 1)
        self.assertEqual(Account.objects.get(bank=True).balance, -20)
        self.assertEqual(Account.objects.get(bank=False).balance, 20)

    def test_bank_receiving_add_view_fail_fiscal_year(self):
        '''
        A `POST` to the ``add_bank_entry`` view with a ``journal_type`` of
        ``CR`` and a ``date`` before the start of the current ``FiscalYear``
        will not create a BankReceivingEntry or Transactions and displays an
        error message.
        If there is only one FiscalYear, the ``period`` amount of months before
        the ``end_month`` is used.
        '''
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        response = self.client.post(reverse('accounts.views.add_bank_entry', kwargs={'journal_type': 'CR'}),
                                    data={'entry-account': self.bank_account.id,
                                          'entry-date': '2011-01-11',
                                          'entry-payor': 'test payor',
                                          'entry-amount': 20,
                                          'entry-memo': 'test memo',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 0,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': '',
                                          'transaction-0-bankspend_entry': '',
                                          'transaction-0-detail': 'test detail',
                                          'transaction-0-amount': 20,
                                          'transaction-0-account': self.expense_account.id,
                                          'subbtn': 'Submit',
                                          })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['entry_form'].is_valid())
        self.assertFormError(response, 'entry_form', 'date',
                'The date must be in the current Fiscal Year.')
        self.assertEqual(BankReceivingEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_bank_receiving_add_view_two_fiscal_year(self):
        '''
        A `POST` to the ``add_bank_entry`` view with a ``journal_type`` of
        ``CR`` and a ``date`` on or after the start of the current
        ``FiscalYear`` will create a BankReceivingEntry and Transactions.
        If there is are multiple FiscalYear, the ``date`` cannot be before the
        ``end_month`` of the Second to Latest FiscalYear.
        '''
        FiscalYear.objects.create(year=2010, end_month=12, period=12)
        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        response = self.client.post(reverse('accounts.views.add_bank_entry', kwargs={'journal_type': 'CR'}),
                                    data={'entry-account': self.bank_account.id,
                                          'entry-date': '2013-03-12',
                                          'entry-payor': 'test payor',
                                          'entry-amount': 20,
                                          'entry-memo': 'test memo',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 0,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': '',
                                          'transaction-0-bankspend_entry': '',
                                          'transaction-0-detail': 'test detail',
                                          'transaction-0-amount': 20,
                                          'transaction-0-account': self.expense_account.id,
                                          'subbtn': 'Submit',
                                          })
        self.assertRedirects(response, reverse('accounts.views.show_bank_entry',
                                               kwargs={'journal_type': 'CR', 'journal_id': 1}))
        self.assertEqual(BankReceivingEntry.objects.count(), 1)
        self.assertEqual(Account.objects.get(bank=True).balance, -20)
        self.assertEqual(Account.objects.get(bank=False).balance, 20)

    def test_bank_receiving_add_view_fail_two_fiscal_year(self):
        '''
        A `POST` to the ``add_bank_entry`` view with a ``journal_type`` of
        ``CR`` and a ``date`` before the start of the current ``FiscalYear``
        will not create a BankReceivingEntry or Transactions and displays an
        error message.
        If there is are multiple FiscalYear, the ``date`` cannot be before the
        ``end_month`` of the Second to Latest FiscalYear.
        '''
        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        response = self.client.post(reverse('accounts.views.add_bank_entry', kwargs={'journal_type': 'CR'}),
                                    data={'entry-account': self.bank_account.id,
                                          'entry-date': '2011-01-11',
                                          'entry-payor': 'test payor',
                                          'entry-amount': 20,
                                          'entry-memo': 'test memo',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 0,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': '',
                                          'transaction-0-bankspend_entry': '',
                                          'transaction-0-detail': 'test detail',
                                          'transaction-0-amount': 20,
                                          'transaction-0-account': self.expense_account.id,
                                          'subbtn': 'Submit',
                                          })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['entry_form'].is_valid())
        self.assertFormError(response, 'entry_form', 'date',
                'The date must be in the current Fiscal Year.')
        self.assertEqual(BankReceivingEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_bank_receiving_add_view_post_fail(self):
        '''
        A `POST` to the `add_bank_entry` view with no submit value will return a
        404
        '''
        response = self.client.post(reverse('accounts.views.add_bank_entry',
                                            kwargs={'journal_id': 9001,
                                                    'journal_type': 'CR'}))
        self.assertEqual(response.status_code, 404)

    def test_bank_receiving_show_view(self):
        '''
        A `GET` to the `show_bank_entry` view with a journal type of `CD` and a
        journal_id will retrieve a BankReceivingEntry passing the respective
        journal_entry, main_transaction and transaction set
        '''
        self.test_bank_receiving_add_view_success()
        response = self.client.get(reverse('accounts.views.show_bank_entry',
                                           kwargs={'journal_type': 'CR', 'journal_id': 1}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/entry_bankreceive_detail.html')
        self.failUnless(isinstance(response.context['journal_entry'], BankReceivingEntry))
        self.assertEqual(BankReceivingEntry.objects.all()[0], response.context['journal_entry'])
        self.assertItemsEqual(response.context['journal_entry'].transaction_set.all(), response.context['transactions'])
        self.assertEqual(response.context['journal_entry'].main_transaction, response.context['main_transaction'])

    def test_bank_spending_add_view_initial(self):
        '''
        A `GET` to the `add_bank_entry` view with a `journal_type` of `CD`
        should display BankSpending Forms and Formsets.
        '''
        response = self.client.get(reverse('accounts.views.add_bank_entry', kwargs={'journal_type': 'CD'}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/entry_add.html')
        self.failUnless(isinstance(response.context['entry_form'], BankSpendingForm))
        self.assertEqual(response.context['journal_type'], 'CD')
        self.failUnless(isinstance(response.context['transaction_formset'], BankSpendingTransactionFormSet))

    def test_bank_spending_add_view_success(self):
        '''
        A `POST` to the 'add_bank_entry' view with a `journal_type` of `CD`
        should create a new BankSpendingEntry and issue a redirect.
        '''
        response = self.client.post(reverse('accounts.views.add_bank_entry', kwargs={'journal_type': 'CD'}),
                                    data={'entry-account': self.bank_account.id,
                                          'entry-date': '2013-03-12',
                                          'entry-ach_payment': True,
                                          'entry-payee': 'test payee',
                                          'entry-amount': 20,
                                          'entry-memo': 'test memo',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 0,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': '',
                                          'transaction-0-bankspend_entry': '',
                                          'transaction-0-detail': 'test detail',
                                          'transaction-0-amount': 20,
                                          'transaction-0-account': self.expense_account.id,
                                          'subbtn': 'Submit',
                                          })

        self.assertRedirects(response, reverse('accounts.views.show_bank_entry',
                                               kwargs={'journal_type': 'CD', 'journal_id': 1}))
        self.assertEqual(BankSpendingEntry.objects.count(), 1)
        self.assertEqual(Account.objects.get(bank=True).balance, 20)
        self.assertEqual(Account.objects.get(bank=False).balance, -20)

    def test_bank_spending_add_view_failure_entry(self):
        '''
        A `POST` to the `add_bank_entry` view with a journal type of `CD` with
        invalid entry data will not create a BankSpendingEntry and displays
        an error message.
        '''
        response = self.client.post(reverse('accounts.views.add_bank_entry', kwargs={'journal_type': 'CD'}),
                                    data={'entry-account': self.bank_account.id,
                                          'entry-date': '2013-03-12',
                                          'entry-amount': 20,
                                          'entry-memo': 'test memo',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 0,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': '',
                                          'transaction-0-bankspend_entry': '',
                                          'transaction-0-detail': 'test detail',
                                          'transaction-0-amount': 20,
                                          'transaction-0-account': self.expense_account.id,
                                          'subbtn': 'Submit',
                                          })
        self.assertEqual(response.status_code, 200)
        self.failIf(response.context['entry_form'].is_valid())
        self.assertFormError(response, 'entry_form', None, 'Either A Check Number or ACH status is required.')
        self.assertEqual(BankSpendingEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_bank_spending_add_view_failure_transaction(self):
        '''
        A `POST` to the `add_bank_entry` view with a journal type of `CD` with
        invalid transaction data will not create a BankSpendingEntry and displays
        an error message.
        '''
        response = self.client.post(reverse('accounts.views.add_bank_entry', kwargs={'journal_type': 'CD'}),
                                    data={'entry-account': self.bank_account.id,
                                          'entry-date': '2013-03-12',
                                          'entry-ach_payment': True,
                                          'entry-payee': 'test payee',
                                          'entry-amount': 20,
                                          'entry-memo': 'test memo',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 0,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': '',
                                          'transaction-0-bankspend_entry': '',
                                          'transaction-0-detail': 'test detail',
                                          'transaction-0-amount': 18,
                                          'transaction-0-account': self.expense_account.id,
                                          'subbtn': 'Submit',
                                          })
        self.assertEqual(response.status_code, 200)
        self.failIf(response.context['transaction_formset'].is_valid())
        self.assertEqual(response.context['transaction_formset'].non_form_errors()[0],
                         'Transactions are out of balance.')
        self.assertEqual(BankSpendingEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_bank_spending_add_view_add_another(self):
        '''
        A `POST` to the 'add_bank_entry' view with a `journal_type` of `CD` and
        submit value of `Submit & Add Another` should create a new BankSpendingEntry
        and issue redirect back to the Add page, initializing the entry form with
        last Entries bank_account.
        '''
        response = self.client.post(reverse('accounts.views.add_bank_entry', kwargs={'journal_type': 'CD'}),
                                    data={'entry-account': self.bank_account.id,
                                          'entry-date': '2013-03-12',
                                          'entry-ach_payment': True,
                                          'entry-payee': 'test payee',
                                          'entry-amount': 20,
                                          'entry-memo': 'test memo',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 0,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': '',
                                          'transaction-0-bankspend_entry': '',
                                          'transaction-0-detail': 'test detail',
                                          'transaction-0-amount': 20,
                                          'transaction-0-account': self.expense_account.id,
                                          'subbtn': 'Submit & Add More',
                                          })

        self.assertRedirects(response, reverse('accounts.views.add_bank_entry', kwargs={'journal_type': 'CD'}) + '?bank_account={0}'.format(self.bank_account.id))
        response = self.client.get(response._headers['location'][1])
        self.assertEqual(response.context['entry_form'].initial['account'], str(self.bank_account.id))
        self.assertEqual(BankSpendingEntry.objects.count(), 1)
        self.assertEqual(Account.objects.get(bank=True).balance, 20)
        self.assertEqual(Account.objects.get(bank=False).balance, -20)

    def test_bank_spending_add_view_delete(self):
        '''
        A `POST` to the `add_bank_entry` view with a `journal_id` and
        `journal_type` of 'CD' will delete the BankSpendingEntry and all related
        Transactions, refunding the respective Accounts.
        '''
        self.test_bank_spending_add_view_success()
        entry = BankSpendingEntry.objects.all()[0]

        self.assertEqual(BankSpendingEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertEqual(Account.objects.get(name='bank').balance, 20)
        self.assertEqual(Account.objects.get(name='expense').balance, -20)

        response = self.client.post(reverse('accounts.views.add_bank_entry',
                                            kwargs={'journal_id': entry.id,
                                                    'journal_type': 'CD'}),
                                    data={'delete': 'Delete'})

        self.assertRedirects(response, reverse('accounts.views.bank_register',
                                               kwargs={'account_slug': self.bank_account.slug}))
        self.assertEqual(BankSpendingEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(Account.objects.get(name='bank').balance, 0)
        self.assertEqual(Account.objects.get(name='expense').balance, 0)

    def test_bank_spending_add_view_delete_fail(self):
        '''
        A `POST` to the `add_bank_entry` view with an invalid `journal_id` and
        `journal_type` of 'CD' will return a 404
        '''
        self.assertEqual(BankSpendingEntry.objects.count(), 0)
        response = self.client.post(reverse('accounts.views.add_bank_entry',
                                            kwargs={'journal_id': 9001,
                                                    'journal_type': 'CD'}),
                                    data={'delete': 'Delete'})
        self.assertEqual(response.status_code, 404)

    def test_bank_spending_add_view_edit(self):
        '''
        A `GET` to the `add_bank_entry` view with a `journal_type` of `CD` and
        a `journal_id` should display BankSpending Forms and Formsets editing
        the BankSpendingEntry with id of `journal_id`.
        '''
        self.test_bank_spending_add_view_success()
        entry = BankSpendingEntry.objects.all()[0]
        response = self.client.get(reverse('accounts.views.add_bank_entry',
                                           kwargs={'journal_type': 'CD',
                                                   'journal_id': entry.id}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/entry_add.html')
        self.failUnless(isinstance(response.context['entry_form'], BankSpendingForm))
        self.failUnless(isinstance(response.context['transaction_formset'], BankSpendingTransactionFormSet))
        self.assertEqual(response.context['entry_form'].instance, entry)
        self.assertEqual(response.context['entry_form'].initial['amount'],
                         entry.main_transaction.balance_delta)
        self.assertEqual(response.context['entry_form'].initial['account'],
                         entry.main_transaction.account)
        self.assertEqual(response.context['transaction_formset'].forms[0].instance,
                         entry.transaction_set.all()[0])
        self.assertEqual(response.context['transaction_formset'].forms[0].initial['amount'],
                         -1 * entry.transaction_set.all()[0].balance_delta)

    def test_bank_spending_add_view_edit_in_fiscal_year(self):
        '''
        A `GET` to the `add_bank_entry` view with a `journal_type` of `CD` and
        a `journal_id` should display BankSpending Forms and Formsets editing
        the BankSpendingEntry with id of `journal_id` if the `date`
        is in the current FiscalYear.
        '''
        FiscalYear.objects.create(year=2013, end_month=12, period=12)
        self.test_bank_spending_add_view_success()
        entry = BankSpendingEntry.objects.all()[0]
        response = self.client.get(reverse('accounts.views.add_bank_entry',
                                           kwargs={'journal_type': 'CD',
                                                   'journal_id': entry.id}))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/entry_add.html')

    def test_bank_spending_add_view_edit_out_of_fiscal_year(self):
        '''
        A `GET` to the `add_bank_entry` view with a `journal_type` of `CD` and
        a `journal_id` will return a 404 Error if the entry is before the
        current Fiscal Year.
        '''
        self.test_bank_spending_add_view_success()
        FiscalYear.objects.create(year=2015, end_month=12, period=12)
        entry = BankSpendingEntry.objects.all()[0]
        response = self.client.get(reverse('accounts.views.add_bank_entry',
                                           kwargs={'journal_type': 'CD',
                                                   'journal_id': entry.id}))

        self.assertEqual(response.status_code, 404)

    def test_bank_spending_add_view_edit_success(self):
        '''
        A `POST` to the 'add_bank_entry' view with a `journal_type` of `CD` with
        a `journal_id` should edit the respective BankSpendingEntry and issue a
        redirect.
        '''
        self.test_bank_spending_add_view_success()
        new_bank_account = create_account('2nd bank', self.asset_header, 0, 1, True)
        new_expense_account = create_account('2nd expense', self.expense_header, 0, 6)
        response = self.client.post(reverse('accounts.views.add_bank_entry', kwargs={'journal_type': 'CD',
                                                                                     'journal_id': 1}),
                                    data={'entry-account': new_bank_account.id,
                                          'entry-date': '12/12/12',
                                          'entry-check_number': 2177,
                                          'entry-payee': 'new payee',
                                          'entry-amount': 20,
                                          'entry-memo': 'new memo',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 1,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': 2,
                                          'transaction-0-bankspend_entry': 1,
                                          'transaction-0-detail': 'test detail',
                                          'transaction-0-amount': 15,
                                          'transaction-0-account': new_expense_account.id,
                                          'transaction-1-id': '',
                                          'transaction-1-bankspend_entry': 1,
                                          'transaction-1-detail': 'test detail 2',
                                          'transaction-1-amount': 5,
                                          'transaction-1-account': self.expense_account.id,
                                          'subbtn': 'Submit',
                                          })
        self.assertRedirects(response, reverse('accounts.views.show_bank_entry',
                                               kwargs={'journal_type': 'CD', 'journal_id': 1}))
        self.assertEqual(BankSpendingEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 3)
        entry = BankSpendingEntry.objects.all()[0]
        self.assertEqual(entry.date, datetime.date(2012, 12, 12))
        self.assertEqual(entry.memo, 'new memo')
        self.assertEqual(entry.payee, 'new payee')
        self.assertEqual(entry.main_transaction.balance_delta, 20)
        bank_account = Account.objects.get(name='bank')
        expense_account = Account.objects.get(name='expense')
        new_bank_account = Account.objects.get(name='2nd bank')
        new_expense_account = Account.objects.get(name='2nd expense')
        self.assertEqual(bank_account.balance, 0)
        self.assertEqual(expense_account.balance, -5)
        self.assertEqual(new_bank_account.balance, 20)
        self.assertEqual(new_expense_account.balance, -15)
        self.assertEqual(new_bank_account, Transaction.objects.all()[0].account)
        self.assertEqual(new_expense_account, Transaction.objects.all()[1].account)

    def test_bank_spending_add_view_fiscal_year(self):
        '''
        A `POST` to the ``add_bank_entry`` view with a ``journal_type`` of
        ``CD`` and a ``date`` on or after the start of the current
        ``FiscalYear`` will create a BankReceivingEntry and Transactions.
        If there is only one FiscalYear, the ``period`` amount of months before
        the ``end_month`` is used.
        '''
        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        response = self.client.post(reverse('accounts.views.add_bank_entry', kwargs={'journal_type': 'CD'}),
                                    data={'entry-account': self.bank_account.id,
                                          'entry-date': '2013-03-12',
                                          'entry-ach_payment': True,
                                          'entry-payee': 'test payee',
                                          'entry-amount': 20,
                                          'entry-memo': 'test memo',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 0,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': '',
                                          'transaction-0-bankspend_entry': '',
                                          'transaction-0-detail': 'test detail',
                                          'transaction-0-amount': 20,
                                          'transaction-0-account': self.expense_account.id,
                                          'subbtn': 'Submit',
                                          })

        self.assertRedirects(response, reverse('accounts.views.show_bank_entry',
                                               kwargs={'journal_type': 'CD', 'journal_id': 1}))
        self.assertEqual(BankSpendingEntry.objects.count(), 1)
        self.assertEqual(Account.objects.get(bank=True).balance, 20)
        self.assertEqual(Account.objects.get(bank=False).balance, -20)

    def test_bank_spending_add_view_fail_fiscal_year(self):
        '''
        A `POST` to the ``add_bank_entry`` view with a ``journal_type`` of
        ``CD`` and a ``date`` before the start of the current ``FiscalYear``
        will not create a BankReceivingEntry or Transactions and displays an
        error message.
        If there is only one FiscalYear, the ``period`` amount of months before
        the ``end_month`` is used.
        '''
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        response = self.client.post(reverse('accounts.views.add_bank_entry', kwargs={'journal_type': 'CR'}),
                                    data={'entry-account': self.bank_account.id,
                                          'entry-date': '2011-01-11',
                                          'entry-payor': 'test payor',
                                          'entry-amount': 20,
                                          'entry-memo': 'test memo',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 0,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': '',
                                          'transaction-0-bankspend_entry': '',
                                          'transaction-0-detail': 'test detail',
                                          'transaction-0-amount': 20,
                                          'transaction-0-account': self.expense_account.id,
                                          'subbtn': 'Submit',
                                          })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['entry_form'].is_valid())
        self.assertFormError(response, 'entry_form', 'date',
                'The date must be in the current Fiscal Year.')
        self.assertEqual(BankSpendingEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_bank_spending_add_view_two_fiscal_year(self):
        '''
        A `POST` to the ``add_bank_entry`` view with a ``journal_type`` of
        ``CD`` and a ``date`` on or after the start of the current
        ``FiscalYear`` will create a BankReceivingEntry and Transactions.
        If there is are multiple FiscalYear, the ``date`` cannot be before the
        ``end_month`` of the Second to Latest FiscalYear.
        '''
        FiscalYear.objects.create(year=2010, end_month=12, period=12)
        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        response = self.client.post(reverse('accounts.views.add_bank_entry', kwargs={'journal_type': 'CR'}),
                                    data={'entry-account': self.bank_account.id,
                                          'entry-date': '2011-01-12',
                                          'entry-payor': 'test payor',
                                          'entry-amount': 20,
                                          'entry-memo': 'test memo',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 0,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': '',
                                          'transaction-0-bankspend_entry': '',
                                          'transaction-0-detail': 'test detail',
                                          'transaction-0-amount': 20,
                                          'transaction-0-account': self.expense_account.id,
                                          'subbtn': 'Submit',
                                          })
        self.assertRedirects(response, reverse('accounts.views.show_bank_entry',
                                               kwargs={'journal_type': 'CR', 'journal_id': 1}))
        self.assertEqual(BankReceivingEntry.objects.count(), 1)
        self.assertEqual(Account.objects.get(bank=True).balance, -20)
        self.assertEqual(Account.objects.get(bank=False).balance, 20)

    def test_bank_spending_add_view_fail_two_fiscal_year(self):
        '''
        A `POST` to the ``add_bank_entry`` view with a ``journal_type`` of
        ``CD`` and a ``date`` before the start of the current ``FiscalYear``
        will not create a BankReceivingEntry or Transactions and displays an
        error message.
        If there is are multiple FiscalYear, the ``date`` cannot be before the
        ``end_month`` of the Second to Latest FiscalYear.
        '''
        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        response = self.client.post(reverse('accounts.views.add_bank_entry', kwargs={'journal_type': 'CR'}),
                                    data={'entry-account': self.bank_account.id,
                                          'entry-date': '2011-01-11',
                                          'entry-payor': 'test payor',
                                          'entry-amount': 20,
                                          'entry-memo': 'test memo',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 0,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': '',
                                          'transaction-0-bankspend_entry': '',
                                          'transaction-0-detail': 'test detail',
                                          'transaction-0-amount': 20,
                                          'transaction-0-account': self.expense_account.id,
                                          'subbtn': 'Submit',
                                          })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['entry_form'].is_valid())
        self.assertFormError(response, 'entry_form', 'date',
                'The date must be in the current Fiscal Year.')
        self.assertEqual(BankSpendingEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_bank_spending_add_view_post_fail(self):
        '''
        A `POST` to the `add_bank_entry` view with no value for submit will
        return a 404.
        '''
        response = self.client.post(reverse('accounts.views.add_bank_entry',
                                            kwargs={'journal_id': 9001,
                                                    'journal_type': 'CD'}))
        self.assertEqual(response.status_code, 404)

    def test_bank_spending_show_view(self):
        '''
        A `GET` to the `show_bank_entry` view with a journal type of `CD` and a
        journal_id will retrieve the respective BankSpendingEntry
        '''
        self.test_bank_spending_add_view_success()
        response = self.client.get(reverse('accounts.views.show_bank_entry',
                                           kwargs={'journal_type': 'CD', 'journal_id': 1}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/entry_bankspend_detail.html')
        self.failUnless(isinstance(response.context['journal_entry'], BankSpendingEntry))
        self.assertEqual(BankSpendingEntry.objects.all()[0], response.context['journal_entry'])
        self.assertItemsEqual(response.context['journal_entry'].transaction_set.all(), response.context['transactions'])
        self.assertEqual(response.context['journal_entry'].main_transaction, response.context['main_transaction'])


class JournalLedgerViewTests(TestCase):
    '''
    Test view for showing all General Journal Entries in a time period
    '''
    def setUp(self):
        self.asset_header = create_header('asset', cat_type=1)
        self.liability_header = create_header('liability', cat_type=2)
        self.bank_account = create_account('bank', self.asset_header, 0, 1, True)
        self.liability_account = create_account('liability', self.liability_header, 0, 2)

    def test_journal_ledger_view_initial(self):
        '''
        A `GET` to the `journal_ledger` view should return a DateRangeForm, start/stopdate
        from 1st of Month to Today and only JournalEntries in this time period.
        '''
        today = datetime.date.today()
        entry = create_entry(today, 'in range entry')
        another_entry = create_entry(today, 'another in range entry')
        create_entry(datetime.date(today.year + 20, 1, 1), 'future entry')
        create_entry(datetime.date(today.year - 20, 1, 1), 'past entry')

        response = self.client.get(reverse('accounts.views.journal_ledger'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/journal_ledger.html')
        self.failUnless(isinstance(response.context['form'], DateRangeForm))
        self.assertEqual(response.context['startdate'], datetime.date(today.year, today.month, 1))
        self.assertEqual(response.context['stopdate'], today)
        self.assertSequenceEqual(response.context['journal_entries'],
                                 [entry, another_entry])

    def test_journal_ledger_view_date_success(self):
        '''
        A `GET` to the `journal_ledger` view with a startdate and stopdate should
        return only JournalEntries from that time period.
        '''
        today = datetime.date.today()
        date_range = (datetime.date(today.year, 4, 1), datetime.date(today.year, 5, 1))
        entry = create_entry(datetime.date(today.year, 4, 20), 'in range entry')
        another_entry = create_entry(datetime.date(today.year, 4, 21), 'another in range entry')
        create_entry(datetime.date(today.year + 20, 4, 20), 'future entry')
        create_entry(datetime.date(today.year - 20, 7, 7), 'past entry')

        response = self.client.get(reverse('accounts.views.journal_ledger'),
                                   data={'startdate': date_range[0], 'stopdate': date_range[1]})

        self.assertEqual(response.status_code, 200)
        self.failUnless(response.context['form'].is_bound)
        self.assertEqual(response.context['startdate'], date_range[0])
        self.assertEqual(response.context['stopdate'], date_range[1])
        self.assertSequenceEqual(response.context['journal_entries'],
                                 [entry, another_entry])

    def test_journal_ledger_view_date_fail(self):
        '''
        A `GET` to the `journal_ledger` view with an invalid startdate and stopdate
        should return a bound DateRangeForm with respective errors.
        '''
        response = self.client.get(reverse('accounts.views.journal_ledger'),
                                   data={'startdate': 'zerocool', 'stopdate': 'foobar'})
        self.assertEqual(response.status_code, 200)
        self.failUnless(response.context['form'].is_bound)
        self.assertFormError(response, 'form', 'startdate', 'Enter a valid date.')
        self.assertFormError(response, 'form', 'stopdate', 'Enter a valid date.')


class BankRegisterViewTests(TestCase):
    '''
    Test view for showing Bank Entry register for a Bank Account
    '''

    def setUp(self):
        '''
        Bank Entries require a Bank Account and a normal Account
        '''
        self.asset_header = create_header('asset', cat_type=1)
        self.liability_header = create_header('liability', cat_type=2)
        self.bank_account = create_account('bank', self.asset_header, 0, 1, True)
        self.liability_account = create_account('liability', self.liability_header, 0, 2)

    def test_bank_register_view_initial(self):
        '''
        A `GET` to the `show_bank_register` view should return a list of
        BankSpendingEntries and BankReceivingEntries associated with the bank
        account, from the beginning of this month to today
        '''
        main_receive = Transaction.objects.create(account=self.bank_account, balance_delta=-20, detail='bank rec')
        receive = BankReceivingEntry.objects.create(main_transaction=main_receive, date=datetime.date.today(),
                                     memo='receive entry',
                                     payor='test payor')
        Transaction.objects.create(bankreceive_entry=receive, account=self.liability_account, balance_delta=20, detail='acc rec')

        main_spend = Transaction.objects.create(account=self.bank_account, balance_delta=50, detail='bank spend')
        spend = BankSpendingEntry.objects.create(main_transaction=main_spend, date=datetime.date.today(), memo='spend entry',
                                  ach_payment=True, payee='test payee')
        Transaction.objects.create(bankspend_entry=spend, account=self.liability_account, balance_delta=-50, detail='acc spend')
        response = self.client.get(reverse('accounts.views.bank_register',
                                   kwargs={'account_slug': self.bank_account.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/bank_register.html')
        self.failUnless(isinstance(response.context['form'], DateRangeForm))
        self.assertItemsEqual(response.context['transactions'],
                              Transaction.objects.filter(account=self.bank_account))
        today = datetime.date.today()
        self.assertEqual(response.context['startdate'], datetime.date(today.year, today.month, 1))
        self.assertEqual(response.context['stopdate'], today)

    def test_bank_register_view_date_filter(self):
        '''
        A `GET` to the `show_bank_register` view submitted with a `start_date`
        and `stop_date` returns the Bank Entries for the account during the time
        period
        '''
        date_range = ('1/1/11', '3/7/12')
        in_range_date = datetime.date(2012, 1, 1)
        out_range_date = datetime.date(2013, 5, 8)
        out_range_date2 = datetime.date(2010, 12, 1)

        banktran_receive = Transaction.objects.create(account=self.bank_account, balance_delta=-20)
        receive = BankReceivingEntry.objects.create(main_transaction=banktran_receive, date=in_range_date, memo='receive entry',
                                     payor='test payor')
        Transaction.objects.create(bankreceive_entry=receive, account=self.liability_account, balance_delta=20)

        banktran_spend = Transaction.objects.create(account=self.bank_account, balance_delta=50)
        spend = BankSpendingEntry.objects.create(main_transaction=banktran_spend, date=in_range_date, memo='spend entry',
                                                 ach_payment=True, payee='test payee')
        Transaction.objects.create(bankspend_entry=spend, account=self.liability_account, balance_delta=-50)

        out_tran1 = Transaction.objects.create(account=self.bank_account, balance_delta=-20)
        out_receive = BankReceivingEntry.objects.create(main_transaction=out_tran1, date=out_range_date2, memo='newer receive entry',
                                         payor='test payor')
        Transaction.objects.create(bankreceive_entry=out_receive, account=self.liability_account, balance_delta=20)

        out_tran2 = Transaction.objects.create(account=self.bank_account, balance_delta=50)
        out_spend = BankSpendingEntry.objects.create(main_transaction=out_tran2, date=out_range_date, memo='older spend entry',
                                                     ach_payment=True, payee='test payee')
        Transaction.objects.create(bankspend_entry=out_spend, account=self.liability_account, balance_delta=-50)

        response = self.client.get(reverse('accounts.views.bank_register', args=[self.bank_account.slug]),
                                   data={'startdate': date_range[0],
                                         'stopdate': date_range[1]})

        self.assertEqual(response.status_code, 200)
        self.assertItemsEqual(response.context['transactions'], [banktran_receive, banktran_spend])
        self.assertEqual(response.context['startdate'], datetime.date(2011, 1, 1))
        self.assertEqual(response.context['stopdate'], datetime.date(2012, 3, 7))


class FiscalYearViewTests(TestCase):
    '''
    Test the view for creating new Fiscal Years.
    '''
    def setUp(self):
        '''
        Fiscal Years need Accounts to clear Transactions from.
        Equity Accounts named ``Retained Earnings`` and ``Current Year
        Earnings`` is required to move balances after purging.
        '''
        self.asset_header = create_header('asset', cat_type=1)
        self.expense_header = create_header('expense', cat_type=6)
        self.bank_account = create_account('bank', self.asset_header, 0, 1, True)
        self.bank_account.last_reconciled = datetime.date(2012, 11, 1)
        self.bank_account.save()
        self.expense_account = create_account('expense', self.expense_header, 0, 6)
        self.equity_header = create_header('Equity', cat_type=3)
        self.retained_account = create_account('Retained Earnings', self.equity_header, 0, 3)
        self.current_earnings = create_account('Current Year Earnings', self.equity_header, 0, 3)

    def test_add_fiscal_year_initial(self):
        '''
        A `GET` to the ``add_fiscal_year`` view should display a FiscalYearForm
        and FiscalYearAccountsFormSet.
        '''
        response = self.client.get(reverse('accounts.views.add_fiscal_year'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/year_add.html')
        self.assertTrue(isinstance(response.context['fiscal_year_form'],
                                   FiscalYearForm))
        self.assertTrue(isinstance(response.context['accounts_formset'],
                                   FiscalYearAccountsFormSet))
        self.assertFalse(response.context['previous_year'])

    def test_add_fiscal_year_success(self):
        '''
        A ``POST`` to the ``add_fiscal_year`` view with valid data will
        create a new ``FiscalYear`` and redirect to the ``show_accounts_chart``
        view.
        '''
        response = self.client.post(reverse('accounts.views.add_fiscal_year'),
                                    {'year': 2013,
                                     'end_month': 12,
                                     'period': 12,
                                     'form-TOTAL_FORMS': 2,
                                     'form-INITIAL_FORMS': 2,
                                     'form-MAX_NUM_FORMS': 2,
                                     'form-0-id': self.bank_account.id,
                                     'form-0-exclude': True,
                                     'form-1-id': self.expense_account.id,
                                     'form-1-exclude': False,
                                     'submit': 'Start New Year'})
        self.assertRedirects(response,
                             reverse('accounts.views.show_accounts_chart'))
        self.assertEqual(FiscalYear.objects.count(), 1)

    def test_add_fiscal_year_post_fail(self):
        '''
        A ``POST`` to the ``add_fiscal_year`` view with invalid data will
        return a bound ``FiscalYearForm`` with the errors.
        '''
        response = self.client.post(reverse('accounts.views.add_fiscal_year'),
                                    {'year': 'over 9000',
                                     'end_month': 15,
                                     'period': 11,
                                     'form-TOTAL_FORMS': 2,
                                     'form-INITIAL_FORMS': 2,
                                     'form-MAX_NUM_FORMS': 2,
                                     'form-0-id': self.bank_account.id,
                                     'form-0-exclude': 'yes',
                                     'form-1-id': self.expense_account.id,
                                     'form-1-exclude': 'whatever',
                                     'submit': 'Start New Year'})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/year_add.html')
        self.assertFormError(response, 'fiscal_year_form', 'year',
                'Enter a whole number.')
        self.assertFormError(response, 'fiscal_year_form', 'end_month',
                "Select a valid choice. 15 is not one of the available "
                "choices.")
        self.assertFormError(response, 'fiscal_year_form', 'period',
                'Select a valid choice. 11 is not one of the available '
                'choices.')

    def test_add_fiscal_year_create_historical_accounts(self):
        '''
        A ``POST`` to the ``add_fiscal_year`` view with valid data and no
        previous FiscalYear will not create any HistoricalAccount entries.
        '''
        self.client.post(reverse('accounts.views.add_fiscal_year'),
                                    {'year': 2013,
                                     'end_month': 12,
                                     'period': 12,
                                     'form-TOTAL_FORMS': 2,
                                     'form-INITIAL_FORMS': 2,
                                     'form-MAX_NUM_FORMS': 2,
                                     'form-0-id': self.bank_account.id,
                                     'form-0-exclude': True,
                                     'form-1-id': self.expense_account.id,
                                     'form-1-exclude': False,
                                     'submit': 'Start New Year'})

        self.assertEqual(HistoricalAccount.objects.count(), 0)

    def test_add_fiscal_year_purge_entries(self):
        '''
        A ``POST`` to the ``add_fiscal_year`` view with valid data and no
        previous ``FiscalYear`` will delete no ``JournalEntry``,
        ``BankReceivingEntry``, or ``BankSpendingEntry`` instances.
        '''
        date = datetime.date(2012, 3, 20)
        entry = create_entry(date, 'reconciled entry')
        bank_trans = create_transaction(entry, self.bank_account, 20)
        bank_trans.reconciled = True
        bank_trans.save()
        create_transaction(entry, self.expense_account, 20)
        unreconciled_entry = create_entry(date, 'unreconciled entry')
        create_transaction(unreconciled_entry, self.bank_account, 35)
        create_transaction(unreconciled_entry, self.expense_account, 20)
        self.client.post(reverse('accounts.views.add_fiscal_year'),
                                    {'year': 2013,
                                     'end_month': 12,
                                     'period': 12,
                                     'form-TOTAL_FORMS': 2,
                                     'form-INITIAL_FORMS': 2,
                                     'form-MAX_NUM_FORMS': 2,
                                     'form-0-id': self.bank_account.id,
                                     'form-0-exclude': True,
                                     'form-1-id': self.expense_account.id,
                                     'form-1-exclude': False,
                                     'submit': 'Start New Year'})
        self.assertEqual(Transaction.objects.count(), 4)

    def test_add_fiscal_year_balance_change(self):
        '''
        A ``POST`` to the ``add_fiscal_year`` view with valid data and no
        previous ``FiscalYear`` will not change ``Account`` balances.
        '''
        date = datetime.date(2012, 3, 20)
        entry = create_entry(date, 'reconciled entry')
        bank_trans = create_transaction(entry, self.bank_account, 20)
        bank_trans.reconciled = True
        bank_trans.save()
        create_transaction(entry, self.expense_account, 20)
        purged_entry = create_entry(date, 'unreconciled but not excluded')
        create_transaction(purged_entry, self.expense_account, -20)
        create_transaction(purged_entry, self.current_earnings, 20)
        unreconciled_entry = create_entry(date, 'unreconciled entry')
        create_transaction(unreconciled_entry, self.bank_account, 35)
        create_transaction(unreconciled_entry, self.expense_account, 20)
        self.client.post(reverse('accounts.views.add_fiscal_year'),
                                    {'year': 2013,
                                     'end_month': 12,
                                     'period': 12,
                                     'form-TOTAL_FORMS': 2,
                                     'form-INITIAL_FORMS': 2,
                                     'form-MAX_NUM_FORMS': 2,
                                     'form-0-id': self.bank_account.id,
                                     'form-0-exclude': True,
                                     'form-1-id': self.expense_account.id,
                                     'form-1-exclude': False,
                                     'submit': 'Start New Year'})
        self.bank_account = Account.objects.get(id=self.bank_account.id)
        self.expense_account = Account.objects.get(id=self.expense_account.id)
        self.current_earnings = Account.objects.get(id=self.current_earnings.id)
        self.retained_account = Account.objects.get(id=self.retained_account.id)
        self.assertEqual(self.bank_account.balance, 55)
        self.assertEqual(self.expense_account.balance, 20)
        self.assertEqual(self.current_earnings.balance, 20)
        self.assertEqual(self.retained_account.balance, 0)

    def test_add_fiscal_year_with_previous_initial(self):
        '''
        If there is a previous FiscalYear, a ``GET`` to the ``add_fiscal_year``
        view should display a FiscalYearForm, FiscalYearAccountsFormSet and the
        previous FiscalYear.
        '''
        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        prev = FiscalYear.objects.create(year=2012, end_month=12, period=12)
        response = self.client.get(reverse('accounts.views.add_fiscal_year'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/year_add.html')
        self.assertTrue(isinstance(response.context['fiscal_year_form'],
                                   FiscalYearForm))
        self.assertTrue(isinstance(response.context['accounts_formset'],
                                   FiscalYearAccountsFormSet))
        self.assertEqual(response.context['previous_year'], prev)

    def test_add_fiscal_year_with_previous_success(self):
        '''
        A ``POST`` to the ``add_fiscal_year`` view with valid data and a
        previous FiscalYear will redirect to the ``show_accounts_chart`` view.
        '''
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        response = self.client.post(reverse('accounts.views.add_fiscal_year'),
                                    {'year': 2013,
                                     'end_month': 12,
                                     'period': 12,
                                     'form-TOTAL_FORMS': 2,
                                     'form-INITIAL_FORMS': 2,
                                     'form-MAX_NUM_FORMS': 2,
                                     'form-0-id': self.bank_account.id,
                                     'form-0-exclude': True,
                                     'form-1-id': self.expense_account.id,
                                     'form-1-exclude': False,
                                     'submit': 'Start New Year'})
        self.assertRedirects(response,
                             reverse('accounts.views.show_accounts_chart'))
        self.assertEqual(FiscalYear.objects.count(), 2)

    def test_add_fiscal_year_with_previous_create_historical_accounts(self):
        '''
        A ``POST`` to the ``add_fiscal_year`` view with valid data and one
        previous FiscalYear will create HistoricalAccounts from the previous
        Years end date to ``period`` months before.
        '''
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        self.client.post(reverse('accounts.views.add_fiscal_year'),
                                    {'year': 2013,
                                     'end_month': 12,
                                     'period': 12,
                                     'form-TOTAL_FORMS': 2,
                                     'form-INITIAL_FORMS': 2,
                                     'form-MAX_NUM_FORMS': 2,
                                     'form-0-id': self.bank_account.id,
                                     'form-0-exclude': True,
                                     'form-1-id': self.expense_account.id,
                                     'form-1-exclude': False,
                                     'submit': 'Start New Year'})
        self.assertEqual(HistoricalAccount.objects.count(), 48)

    def test_add_fiscal_year_with_previous_purge_entries(self):
        '''
        A ``POST`` to the ``add_fiscal_year`` view with valid data and one
        previous ``FiscalYear`` will delete all ``JournalEntry``,
        ``BankReceivingEntry``, and ``BankSpendingEntry`` from the previous
        ``FiscalYear`` excluding those with unreconciled ``Transactions``
        for ``Accounts`` in the POSTed data.
        '''
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        date = datetime.date(2012, 3, 20)
        entry = create_entry(date, 'reconciled entry')
        bank_trans = create_transaction(entry, self.bank_account, 20)
        bank_trans.reconciled = True
        bank_trans.save()
        create_transaction(entry, self.expense_account, 20)
        purged_entry = create_entry(date, 'unreconciled but not excluded')
        create_transaction(purged_entry, self.expense_account, -20)
        create_transaction(purged_entry, self.current_earnings, 20)
        unreconciled_entry = create_entry(date, 'unreconciled entry')
        unreconciled_bank = create_transaction(unreconciled_entry, self.bank_account, 35)
        unreconciled_expense = create_transaction(unreconciled_entry, self.expense_account, 20)
        self.client.post(reverse('accounts.views.add_fiscal_year'),
                                    {'year': 2013,
                                     'end_month': 12,
                                     'period': 12,
                                     'form-TOTAL_FORMS': 2,
                                     'form-INITIAL_FORMS': 2,
                                     'form-MAX_NUM_FORMS': 2,
                                     'form-0-id': self.bank_account.id,
                                     'form-0-exclude': True,
                                     'form-1-id': self.expense_account.id,
                                     'form-1-exclude': False,
                                     'submit': 'Start New Year'})
        self.assertEqual(Transaction.objects.count(), 4)    # Includes 2 Transactions
                                                            # for Current Year -> Retained entry
        curr_trans = Account.objects.get(id=self.current_earnings.id).transaction_set.all()[0]
        ret_trans = Account.objects.get(id=self.retained_account.id).transaction_set.all()[0]
        self.assertSequenceEqual(Transaction.objects.all(),
                [unreconciled_bank, unreconciled_expense, curr_trans, ret_trans])

    def test_add_fiscal_year_with_previous_purge_bank_spending_entries(self):
        '''
        A ``POST`` to the ``add_fiscal_year`` view with valid data and one
        previous ``FiscalYear`` will delete all ``JournalEntry``,
        ``BankReceivingEntry``, and ``BankSpendingEntry`` from the previous
        ``FiscalYear`` excluding those with unreconciled ``Transactions``
        for ``Accounts`` in the POSTed data.
        '''
        bank_account2 = create_account('bank2', self.asset_header, 0, 1, True)
        bank_account2.last_reconciled = datetime.date(2012, 11, 1)
        bank_account2.save()
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        date = datetime.date(2012, 3, 20)
        # This Account is excluded but the entry is reconciled.
        entry_main = Transaction.objects.create(account=self.bank_account, balance_delta=20, reconciled=True)
        entry = BankSpendingEntry.objects.create(main_transaction=entry_main,
                date=date, memo='reconciled entry', payee='test payee', ach_payment=True)
        Transaction.objects.create(account=self.expense_account, balance_delta=-20,
                bankspend_entry=entry)
        # This Account is not excluded so the entry will be deleted
        purged_entry_main = Transaction.objects.create(account=bank_account2,
                balance_delta=20, reconciled=False)
        purged_entry = BankSpendingEntry.objects.create(main_transaction=purged_entry_main,
                date=date, memo='unreconiled but not excluded', payee='test payee', ach_payment=True)
        Transaction.objects.create(account=self.expense_account, balance_delta=-20,
                bankspend_entry=purged_entry)
        # This Account is excluded and the entry is unreconciled so it will stay
        unreconciled_bank = Transaction.objects.create(account=self.bank_account,
                balance_delta=20, reconciled=False)
        unreconciled_entry = BankSpendingEntry.objects.create(main_transaction=unreconciled_bank,
                date=date, memo='unreconciled entry', payee='test payee', ach_payment=True)
        unreconciled_expense = Transaction.objects.create(account=self.expense_account, balance_delta=-20,
                bankspend_entry=unreconciled_entry)
        self.client.post(reverse('accounts.views.add_fiscal_year'),
                                    {'year': 2013,
                                     'end_month': 12,
                                     'period': 12,
                                     'form-TOTAL_FORMS': 3,
                                     'form-INITIAL_FORMS': 3,
                                     'form-MAX_NUM_FORMS': 3,
                                     'form-0-id': self.bank_account.id,
                                     'form-0-exclude': True,
                                     'form-1-id': self.expense_account.id,
                                     'form-1-exclude': False,
                                     'form-2-id': bank_account2.id,
                                     'form-2-exclude': False,
                                     'submit': 'Start New Year'})
        self.assertEqual(Transaction.objects.count(), 4)    # Includes 2 Transactions
                                                            # for Current Year -> Retained entry
        curr_trans = Account.objects.get(id=self.current_earnings.id).transaction_set.all()[0]
        ret_trans = Account.objects.get(id=self.retained_account.id).transaction_set.all()[0]
        self.assertSequenceEqual(Transaction.objects.all(),
                [unreconciled_bank, unreconciled_expense, curr_trans, ret_trans])

    def test_add_fiscal_year_with_previous_purge_bank_receiving_entries(self):
        '''
        A ``POST`` to the ``add_fiscal_year`` view with valid data and one
        previous ``FiscalYear`` will delete all ``JournalEntry``,
        ``BankReceivingEntry``, and ``BankSpendingEntry`` from the previous
        ``FiscalYear`` excluding those with unreconciled ``Transactions``
        for ``Accounts`` in the POSTed data.
        '''
        bank_account2 = create_account('bank2', self.asset_header, 0, 1, True)
        bank_account2.last_reconciled = datetime.date(2012, 11, 1)
        bank_account2.save()
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        date = datetime.date(2012, 3, 20)
        # This Account is excluded but the entry is reconciled.
        entry_main = Transaction.objects.create(account=self.bank_account, balance_delta=-20, reconciled=True)
        entry = BankReceivingEntry.objects.create(main_transaction=entry_main,
                date=date, memo='reconciled entry', payor='test payor')
        Transaction.objects.create(account=self.expense_account, balance_delta=20,
                bankreceive_entry=entry)
        # This Account is not excluded so the entry will be deleted
        purged_entry_main = Transaction.objects.create(account=bank_account2,
                balance_delta=-20, reconciled=False)
        purged_entry = BankReceivingEntry.objects.create(main_transaction=purged_entry_main,
                date=date, memo='unreconiled but not excluded', payor='test payor')
        Transaction.objects.create(account=self.expense_account, balance_delta=20,
                bankreceive_entry=purged_entry)
        # This Account is excluded and the entry is unreconciled so it will stay
        unreconciled_bank = Transaction.objects.create(account=self.bank_account,
                balance_delta=-20, reconciled=False)
        unreconciled_entry = BankReceivingEntry.objects.create(main_transaction=unreconciled_bank,
                date=date, memo='unreconciled entry', payor='test payor')
        unreconciled_expense = Transaction.objects.create(account=self.expense_account, balance_delta=20,
                bankreceive_entry=unreconciled_entry)
        self.client.post(reverse('accounts.views.add_fiscal_year'),
                                    {'year': 2013,
                                     'end_month': 12,
                                     'period': 12,
                                     'form-TOTAL_FORMS': 3,
                                     'form-INITIAL_FORMS': 3,
                                     'form-MAX_NUM_FORMS': 3,
                                     'form-0-id': self.bank_account.id,
                                     'form-0-exclude': True,
                                     'form-1-id': self.expense_account.id,
                                     'form-1-exclude': False,
                                     'form-2-id': bank_account2.id,
                                     'form-2-exclude': False,
                                     'submit': 'Start New Year'})
        self.assertEqual(Transaction.objects.count(), 4)    # Includes 2 Transactions
                                                            # for Current Year -> Retained entry
        curr_trans = Account.objects.get(id=self.current_earnings.id).transaction_set.all()[0]
        ret_trans = Account.objects.get(id=self.retained_account.id).transaction_set.all()[0]
        self.assertSequenceEqual(Transaction.objects.all(),
                [unreconciled_bank, unreconciled_expense, curr_trans, ret_trans])

    def test_add_fiscal_year_with_previous_balance_changes(self):
        '''
        A ``POST`` to the ``add_fiscal_year`` view with valid data and a
        previous ``FiscalYear`` will set new ``Account`` balances.
        Accounts with types 1-3 will have their balance set to the last

        HistoricalAccount of the just completed FiscalYear, plus any
        Transactions in the new FiscalYear.

        Accounts with type 4-8 will have their balance set to the sum of its
        Transactions balance_deltas in the new FiscalYear.

        The balance of the ``Current Year Earnings`` account will be moved
        to the ``Retained Earnings`` account.
        '''
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        other_expense_account = create_account('Other Expense', self.expense_header, 0, 6)
        date = datetime.date(2012, 3, 20)
        entry = create_entry(date, 'reconciled entry')
        bank_trans = create_transaction(entry, self.bank_account, 20)
        bank_trans.reconciled = True
        bank_trans.save()
        create_transaction(entry, self.expense_account, 20)
        purged_entry = create_entry(date, 'unreconciled but not excluded')
        create_transaction(purged_entry, self.expense_account, -20)
        create_transaction(purged_entry, self.current_earnings, 20)
        unreconciled_entry = create_entry(date, 'unreconciled entry')
        create_transaction(unreconciled_entry, self.bank_account, 35)
        create_transaction(unreconciled_entry, self.expense_account, 20)
        future_date = datetime.date(2013, 2, 1)
        future_entry = create_entry(future_date, 'in new fiscal year')
        create_transaction(future_entry, other_expense_account, 2)
        self.client.post(reverse('accounts.views.add_fiscal_year'),
                                    {'year': 2013,
                                     'end_month': 12,
                                     'period': 12,
                                     'form-TOTAL_FORMS': 2,
                                     'form-INITIAL_FORMS': 2,
                                     'form-MAX_NUM_FORMS': 2,
                                     'form-0-id': self.bank_account.id,
                                     'form-0-exclude': True,
                                     'form-1-id': self.expense_account.id,
                                     'form-1-exclude': False,
                                     'submit': 'Start New Year'})
        self.bank_account = Account.objects.get(id=self.bank_account.id)
        self.expense_account = Account.objects.get(id=self.expense_account.id)
        other_expense_account = Account.objects.get(id=other_expense_account.id)
        self.current_earnings = Account.objects.get(id=self.current_earnings.id)
        self.retained_account = Account.objects.get(id=self.retained_account.id)
        self.assertEqual(self.bank_account.balance, 55)
        self.assertEqual(self.expense_account.balance, 0)
        self.assertEqual(other_expense_account.balance, 2)
        self.assertEqual(self.current_earnings.balance, 0)
        self.assertEqual(self.retained_account.balance, 20)

    def test_add_fiscal_year_w_two_previous_create_historical_accounts(self):
        '''
        A ``POST`` to the ``add_fiscal_year`` view with valid data and two
        previous FiscalYear will create HistoricalAccount entries for the
        time period of the previous FiscalYear.

        HistoricalAccounts with a ``type`` between 1 and 3 will have balance
        sums per month while those with a ``type`` between 4 and 8 will have
        the net_change for the month.
        '''
        jan = datetime.date(2012, 1, 20)
        jan_entry = create_entry(jan, 'jan entry')
        create_transaction(jan_entry, self.bank_account, -20)
        create_transaction(jan_entry, self.expense_account, -15)
        create_transaction(jan_entry, self.current_earnings, 35)

        sept = datetime.date(2012, 9, 4)
        sept_entry = create_entry(sept, 'sept entry')
        create_transaction(sept_entry, self.bank_account, -20)
        create_transaction(sept_entry, self.expense_account, -15)
        create_transaction(sept_entry, self.current_earnings, 35)

        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        FiscalYear.objects.create(year=2012, end_month=12, period=12)

        self.client.post(reverse('accounts.views.add_fiscal_year'),
                                    {'year': 2013,
                                     'end_month': 12,
                                     'period': 12,
                                     'form-TOTAL_FORMS': 2,
                                     'form-INITIAL_FORMS': 2,
                                     'form-MAX_NUM_FORMS': 2,
                                     'form-0-id': self.bank_account.id,
                                     'form-0-exclude': True,
                                     'form-1-id': self.expense_account.id,
                                     'form-1-exclude': False,
                                     'submit': 'Start New Year'})
        self.assertEqual(HistoricalAccount.objects.count(), 48)

        jan_bank = HistoricalAccount.objects.get(date__month=1, date__year=2012,
                name=self.bank_account.name)
        jan_exp = HistoricalAccount.objects.get(date__month=1, date__year=2012,
                name=self.expense_account.name)
        jan_earn = HistoricalAccount.objects.get(date__month=1, date__year=2012,
                name=self.current_earnings.name)
        self.assertEqual(jan_bank.amount, -20)
        self.assertEqual(jan_exp.amount, -15)
        self.assertEqual(jan_earn.amount, 35)

        mar_bank = HistoricalAccount.objects.get(date__month=3, date__year=2012,
                name=self.bank_account.name)
        mar_exp = HistoricalAccount.objects.get(date__month=3, date__year=2012,
                name=self.expense_account.name)
        mar_earn = HistoricalAccount.objects.get(date__month=3, date__year=2012,
                name=self.current_earnings.name)
        self.assertEqual(mar_bank.amount, -20)
        self.assertEqual(mar_exp.amount, 0)
        self.assertEqual(mar_earn.amount, 35)

        sept_bank = HistoricalAccount.objects.get(date__month=9, date__year=2012,
                name=self.bank_account.name)
        sept_exp = HistoricalAccount.objects.get(date__month=9, date__year=2012,
                name=self.expense_account.name)
        sept_earn = HistoricalAccount.objects.get(date__month=9, date__year=2012,
                name=self.current_earnings.name)
        self.assertEqual(sept_bank.amount, -40)
        self.assertEqual(sept_exp.amount, -15)
        self.assertEqual(sept_earn.amount, 70)

    def test_add_fiscal_year_w_two_previous_purge_entries(self):
        '''
        A ``POST`` to the ``add_fiscal_year`` view with valid data and two
        previous ``FiscalYears`` will purge all ``JournalEntry``,
        ``BankReceivingEntry`` and ``BankReceivingEntry`` instances in the last
        ``FiscalYear`` excluding Entries containing unreconciled
        ``Transactions`` for ``Accounts`` in the POSTed data.
        '''
        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        date = datetime.date(2012, 3, 20)
        entry = create_entry(date, 'reconciled entry')
        bank_trans = create_transaction(entry, self.bank_account, 20)
        bank_trans.reconciled = True
        bank_trans.save()
        create_transaction(entry, self.expense_account, 20)
        unreconciled_entry = create_entry(date, 'unreconciled entry')
        unreconciled_bank = create_transaction(unreconciled_entry, self.bank_account, 35)
        unreconciled_expense = create_transaction(unreconciled_entry, self.expense_account, 20)
        self.client.post(reverse('accounts.views.add_fiscal_year'),
                                    {'year': 2013,
                                     'end_month': 12,
                                     'period': 12,
                                     'form-TOTAL_FORMS': 2,
                                     'form-INITIAL_FORMS': 2,
                                     'form-MAX_NUM_FORMS': 2,
                                     'form-0-id': self.bank_account.id,
                                     'form-0-exclude': True,
                                     'form-1-id': self.expense_account.id,
                                     'form-1-exclude': False,
                                     'submit': 'Start New Year'})
        self.assertEqual(Transaction.objects.count(), 4)    # Includes 2 Transactions
                                                            # for Current Year -> Retained entry
        curr_trans = Account.objects.get(id=self.current_earnings.id).transaction_set.all()[0]
        ret_trans = Account.objects.get(id=self.retained_account.id).transaction_set.all()[0]
        self.assertSequenceEqual(Transaction.objects.all(),
                [unreconciled_bank, unreconciled_expense, curr_trans, ret_trans])

    def test_add_fiscal_year_w_two_previous_purge_bank_spending_entries(self):
        '''
        A ``POST`` to the ``add_fiscal_year`` view with valid data and two
        previous ``FiscalYears`` will purge all ``JournalEntry``,
        ``BankReceivingEntry`` and ``BankReceivingEntry`` instances in the last
        ``FiscalYear`` excluding Entries containing unreconciled
        ``Transactions`` for ``Accounts`` in the POSTed data.
        '''
        bank_account2 = create_account('bank2', self.asset_header, 0, 1, True)
        bank_account2.last_reconciled = datetime.date(2012, 11, 1)
        bank_account2.save()
        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        date = datetime.date(2012, 3, 20)
        # This Account is excluded but the entry is reconciled.
        entry_main = Transaction.objects.create(account=self.bank_account, balance_delta=20, reconciled=True)
        entry = BankSpendingEntry.objects.create(main_transaction=entry_main,
                date=date, memo='reconciled entry', payee='test payee', ach_payment=True)
        Transaction.objects.create(account=self.expense_account, balance_delta=-20,
                bankspend_entry=entry)
        # This Account is not excluded so the entry will be deleted
        purged_entry_main = Transaction.objects.create(account=bank_account2,
                balance_delta=20, reconciled=False)
        purged_entry = BankSpendingEntry.objects.create(main_transaction=purged_entry_main,
                date=date, memo='unreconiled but not excluded', payee='test payee', ach_payment=True)
        Transaction.objects.create(account=self.expense_account, balance_delta=-20,
                bankspend_entry=purged_entry)
        # This Account is excluded and the entry is unreconciled so it will stay
        unreconciled_bank = Transaction.objects.create(account=self.bank_account,
                balance_delta=20, reconciled=False)
        unreconciled_entry = BankSpendingEntry.objects.create(main_transaction=unreconciled_bank,
                date=date, memo='unreconciled entry', payee='test payee', ach_payment=True)
        unreconciled_expense = Transaction.objects.create(account=self.expense_account, balance_delta=-20,
                bankspend_entry=unreconciled_entry)
        self.client.post(reverse('accounts.views.add_fiscal_year'),
                                    {'year': 2013,
                                     'end_month': 12,
                                     'period': 12,
                                     'form-TOTAL_FORMS': 3,
                                     'form-INITIAL_FORMS': 3,
                                     'form-MAX_NUM_FORMS': 3,
                                     'form-0-id': self.bank_account.id,
                                     'form-0-exclude': True,
                                     'form-1-id': self.expense_account.id,
                                     'form-1-exclude': False,
                                     'form-2-id': bank_account2.id,
                                     'form-2-exclude': False,
                                     'submit': 'Start New Year'})
        self.assertEqual(Transaction.objects.count(), 4)    # Includes 2 Transactions
                                                            # for Current Year -> Retained entry
        curr_trans = Account.objects.get(id=self.current_earnings.id).transaction_set.all()[0]
        ret_trans = Account.objects.get(id=self.retained_account.id).transaction_set.all()[0]
        self.assertSequenceEqual(Transaction.objects.all(),
                [unreconciled_bank, unreconciled_expense, curr_trans, ret_trans])

    def test_add_fiscal_year_w_two_previous_purge_bank_receiving_entries(self):
        '''
        A ``POST`` to the ``add_fiscal_year`` view with valid data and two
        previous ``FiscalYears`` will purge all ``JournalEntry``,
        ``BankReceivingEntry`` and ``BankReceivingEntry`` instances in the last
        ``FiscalYear`` excluding Entries containing unreconciled
        ``Transactions`` for ``Accounts`` in the POSTed data.
        '''
        bank_account2 = create_account('bank2', self.asset_header, 0, 1, True)
        bank_account2.last_reconciled = datetime.date(2012, 11, 1)
        bank_account2.save()
        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        date = datetime.date(2012, 3, 20)
        # This Account is excluded but the entry is reconciled.
        entry_main = Transaction.objects.create(account=self.bank_account, balance_delta=-20, reconciled=True)
        entry = BankReceivingEntry.objects.create(main_transaction=entry_main,
                date=date, memo='reconciled entry', payor='test payor')
        Transaction.objects.create(account=self.expense_account, balance_delta=20,
                bankreceive_entry=entry)
        # This Account is not excluded so the entry will be deleted
        purged_entry_main = Transaction.objects.create(account=bank_account2,
                balance_delta=-20, reconciled=False)
        purged_entry = BankReceivingEntry.objects.create(main_transaction=purged_entry_main,
                date=date, memo='unreconiled but not excluded', payor='test payor')
        Transaction.objects.create(account=self.expense_account, balance_delta=20,
                bankreceive_entry=purged_entry)
        # This Account is excluded and the entry is unreconciled so it will stay
        unreconciled_bank = Transaction.objects.create(account=self.bank_account,
                balance_delta=-20, reconciled=False)
        unreconciled_entry = BankReceivingEntry.objects.create(main_transaction=unreconciled_bank,
                date=date, memo='unreconciled entry', payor='test payor')
        unreconciled_expense = Transaction.objects.create(account=self.expense_account, balance_delta=20,
                bankreceive_entry=unreconciled_entry)
        self.client.post(reverse('accounts.views.add_fiscal_year'),
                                    {'year': 2013,
                                     'end_month': 12,
                                     'period': 12,
                                     'form-TOTAL_FORMS': 3,
                                     'form-INITIAL_FORMS': 3,
                                     'form-MAX_NUM_FORMS': 3,
                                     'form-0-id': self.bank_account.id,
                                     'form-0-exclude': True,
                                     'form-1-id': self.expense_account.id,
                                     'form-1-exclude': False,
                                     'form-2-id': bank_account2.id,
                                     'form-2-exclude': False,
                                     'submit': 'Start New Year'})
        self.assertEqual(Transaction.objects.count(), 4)    # Includes 2 Transactions
                                                            # for Current Year -> Retained entry
        curr_trans = Account.objects.get(id=self.current_earnings.id).transaction_set.all()[0]
        ret_trans = Account.objects.get(id=self.retained_account.id).transaction_set.all()[0]
        self.assertSequenceEqual(Transaction.objects.all(),
                [unreconciled_bank, unreconciled_expense, curr_trans, ret_trans])

    def test_add_fiscal_year_with_previous_purge_entries_main_trans(self):
        '''
        A ``POST`` to the ``add_fiscal_year`` view with valid data and two
        previous ``FiscalYears`` will purge the `main_transactions` of
        ``BankReceivingEntry`` and ``BankReceivingEntry`` instances in the last
        ``FiscalYear`` excluding Entries containing unreconciled
        ``Transactions`` for ``Accounts`` in the POSTed data.

        Tests for regression in bug where `main_transaction` was not being
        deleted in FiscalYear creation.
        '''
        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        date = datetime.date(2012, 3, 20)
        unreconciled_main = Transaction.objects.create(date=date, detail='unrec main',
                account=self.bank_account, balance_delta=50)
        unreconciled_bank_entry = BankSpendingEntry.objects.create(ach_payment=True,
                main_transaction=unreconciled_main, date=date, memo='unreconciled')
        Transaction.objects.create(bankspend_entry=unreconciled_bank_entry,
                balance_delta=-50, account=self.expense_account)
        reconciled_main = Transaction.objects.create(date=date, detail='rec main',
                account=self.bank_account, balance_delta=50, reconciled=True)
        reconciled_bank_entry = BankReceivingEntry.objects.create(payor='test',
                main_transaction=reconciled_main, date=date, memo='reconciled')
        Transaction.objects.create(bankreceive_entry=reconciled_bank_entry, detail='rec gen',
                balance_delta=-50, account=self.expense_account)
        self.client.post(reverse('accounts.views.add_fiscal_year'),
                                    {'year': 2013,
                                     'end_month': 12,
                                     'period': 12,
                                     'form-TOTAL_FORMS': 2,
                                     'form-INITIAL_FORMS': 2,
                                     'form-MAX_NUM_FORMS': 2,
                                     'form-0-id': self.bank_account.id,
                                     'form-0-exclude': True,
                                     'form-1-id': self.expense_account.id,
                                     'form-1-exclude': False,
                                     'submit': 'Start New Year'})
        self.assertTrue(Transaction.objects.filter(detail='unrec main').exists())
        self.assertFalse(Transaction.objects.filter(detail='rec main').exists())
        self.assertFalse(Transaction.objects.filter(detail='rec gen').exists())
        self.assertEqual(BankReceivingEntry.objects.count(), 0)
        self.assertEqual(BankSpendingEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 4)
