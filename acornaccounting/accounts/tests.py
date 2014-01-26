import datetime
from decimal import Decimal

from django.core.urlresolvers import reverse
from django.db.models import ProtectedError
from django.db.utils import IntegrityError
from django.test import TestCase

from core.forms import DateRangeForm
from core.tests import (create_header, create_entry, create_account,
                        create_transaction)
from entries.models import Transaction, BankReceivingEntry, BankSpendingEntry
from fiscalyears.models import FiscalYear

from .models import Account, Header, HistoricalAccount
from .forms import AccountReconcileForm, ReconcileTransactionFormSet


class BaseAccountModelTests(TestCase):
    def test_balance_flip(self):
        """
        Tests that Asset, Expense, Cost of Sales, and Other Expenses
        have there balances flipped.
        (i.e., debiting these account types should _increase_ their value)
        """
        asset_header = create_header('asset', cat_type=1)
        expense_header = create_header('expense', cat_type=6)
        cost_header = create_header('cost', cat_type=5)
        oth_expense_header = create_header('oth_expense', cat_type=8)

        asset_acc = create_account('asset', asset_header, 0, 1)
        expense_acc = create_account('expense', expense_header, 0, 6)
        cost_acc = create_account('cost', cost_header, 0, 5)
        oth_expense_acc = create_account('oth_expense', oth_expense_header,
                                         0, 8)

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

    def test_has_parent_changed_new(self):
        """Test that new instances have had their parent changed."""
        header = Header(name="header", slug="header", parent=None, type=2)
        account = Account(name="account", slug="account", parent=header,
                          balance=0)

        self.assertTrue(header._has_parent_changed())
        self.assertTrue(account._has_parent_changed())

    def test_has_parent_changed_no_change(self):
        """Tests that unchanged instances have not had their parent changed."""
        header = create_header("header")
        account = create_account("account", header, 0)

        self.assertFalse(header._has_parent_changed())
        self.assertFalse(account._has_parent_changed())

    def test_has_parent_changed_parent_change(self):
        """
        The _has_parent_changed method should return True if the parent has
        been changed.
        """
        header = create_header("header")
        account = create_account("account", header, 0)
        other_parent = create_header("other")

        header.parent = other_parent
        account.parent = other_parent

        self.assertTrue(header._has_parent_changed())
        self.assertTrue(account._has_parent_changed())

    def test_has_parent_changed_other_change(self):
        """
        The _has_parent_changed method should return False values other than
        the parent have been changed.
        """
        header = create_header("header")
        account = create_account("account", header, 0)

        header.active = False
        header.name = "this"
        header.type = 1
        header.description = "huh"
        account.active = False
        account.name = "this"
        account.type = 1
        account.description = "huh"
        account.balance = 2
        account.bank = True
        account.last_reconciled = datetime.date.today()

        self.assertFalse(header._has_parent_changed())
        self.assertFalse(account._has_parent_changed())

    def test_get_full_number_calculate_if_none(self):
        """If a saved instance has no number, it should be calculated."""
        header = Header(name="this", slug="this", type=2, parent=None)
        header.save()
        header.full_number = None

        self.assertEqual('2-0000', header.get_full_number())

    def test_get_full_number_of_new_instance(self):
        """The full number of a new unsaved instance should be None."""
        header = create_header("header")
        account = Account(name="this", slug="this", type=2, parent=header)

        self.assertEqual(None, account.get_full_number())


class HeaderModelTests(TestCase):
    def test_get_account_balance(self):
        """
        Tests get_account_balance with only direct children of a Header.
        """
        header = create_header('Initial')
        account = create_account('Account', header, 0)
        entry = create_entry(datetime.date.today(), 'test entry')
        create_transaction(entry, account, -20)
        self.assertEqual(header.get_account_balance(), -20)

    def test_get_account_balance_inherit(self):
        """
        Tests that get_account_balance calculates recursively.
        """
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

    def test_save_recalculate_full_number(self):
        """
        Tests that the save method recalculates new Numbers for the Old and New
        Sibling Headers when a Header's parent is changed.
        """
        self.test_child_node_get_number()
        asset_child = Header.objects.get(slug="asset-child")
        asset_child2_child = Header.objects.get(slug="asset-child-2-child")
        liability_child = Header.objects.get(slug="me-too")

        asset_child2_child.parent = liability_child.parent
        asset_child2_child.type = 2
        asset_child2_child.save()
        asset_child = Header.objects.get(slug="asset-child")
        asset_child2_child = Header.objects.get(slug="asset-child-2-child")
        liability_child = Header.objects.get(slug="me-too")

        self.assertEqual(asset_child.full_number,
                         '{0}-0200'.format(asset_child.type))
        self.assertEqual(liability_child.full_number,
                         '{0}-0200'.format(liability_child.type))
        self.assertEqual(asset_child2_child.full_number,
                         '{0}-0100'.format(asset_child2_child.type))

    def test_save_inherit_type(self):
        """
        Tests that child Headers inherit their root Header's type.
        """
        top_head = create_header('Initial')
        child_head = Header.objects.create(name='Child', parent=top_head, slug='child')
        gchild_head = Header.objects.create(name='gChild', parent=child_head, slug='gchild')
        self.assertEqual(top_head.type, child_head.type)
        self.assertEqual(top_head.type, gchild_head.type)

    def test_save_rootnode_type_fail(self):
        """
        Tests that root Headers require a type.
        """
        head = Header(name='initial', slug='initial', type=None)
        self.assertRaises(IntegrityError, head.save)

    def test_root_node_get_number(self):
        """
        Tests that a root Header number is it's type
        """
        asset = Header.objects.create(name='asset', slug='asset', type=1)
        liability = Header.objects.create(name='liability', slug='liability', type=2)
        self.assertEqual(Header.objects.all()[0].get_full_number(), '{0}-0000'.format(asset.type))
        self.assertEqual(Header.objects.all()[1].get_full_number(), '{0}-0000'.format(liability.type))

    def test_child_node_get_number(self):
        """
        Tests that child Headers are numbered by type and alphabetical tree position
        """
        asset = Header.objects.create(name='asset', slug='asset', type=1)
        asset_child = Header.objects.create(name='I will be second alphabetically', slug='asset-child', parent=asset)
        self.assertEqual(Header.objects.get(id=asset.id).get_full_number(), '{0}-0000'.format(asset.type))
        self.assertEqual(Header.objects.get(id=asset_child.id).get_full_number(), '{0}-0100'.format(asset_child.type))
        asset_child2 = Header.objects.create(name='And I will be first alphabetically', slug='asset-child-2', parent=asset)
        self.assertEqual(Header.objects.get(id=asset_child2.id).get_full_number(), '{0}-0100'.format(asset_child2.type))
        self.assertEqual(Header.objects.get(id=asset_child.id).get_full_number(), '{0}-0200'.format(asset_child.type))
        asset_child2_child = Header.objects.create(name='I will steal spot 2 since I am a child of spot 1', slug='asset-child-2-child', parent=asset_child2)
        self.assertEqual(Header.objects.get(id=asset_child2.id).get_full_number(), '{0}-0100'.format(asset_child2.type))
        self.assertEqual(Header.objects.get(id=asset_child2_child.id).get_full_number(), '{0}-0200'.format(asset_child2_child.type))
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

    def test_save_inherit_type(self):
        """
        Tests that Accounts inherit their type from their root Header.
        """
        self.assertEqual(self.child_acc.type, self.top_head.type)
        self.assertEqual(self.gchild_acc.type, self.top_head.type)

    def test_account_get_number(self):
        """
        Tests that Accounts are numbered according to parent number and
        alphabetical position in siblings list.
        """
        self.child_acc = Account.objects.get(name='child')
        self.gchild_acc = Account.objects.get(name='gChild')
        self.assertEqual(self.child_acc.get_full_number(),
                         '{0}-{1:02d}{2:02d}'.format(
                             self.child_acc.type,
                             self.child_acc.parent.account_number(),
                             self.child_acc.account_number()))
        self.assertEqual(self.gchild_acc.get_full_number(),
                         '{0}-{1:02d}{2:02d}'.format(
                             self.gchild_acc.type,
                             self.gchild_acc.parent.account_number(),
                             self.gchild_acc.account_number()))

    def test_get_balance_by_date(self):
        """
        The ``get_balance_by_date`` function should return the ``Accounts``
        balance at the end of the ``date`` if there is a ``Transaction`` on the
        ``date``.
        """
        date = datetime.date.today()
        entry = create_entry(date, 'entry')
        create_transaction(entry, self.child_acc, 20)
        self.assertEqual(self.child_acc.get_balance_by_date(date), 20)

    def test_get_balance_by_date_flipped(self):
        """
        The ``get_balance_by_date`` function should flip the sign of the
        returned ``balance`` if the ``Account`` is an Asset, Expense, Cost of
        Sale, or Other Expense (indicated by ``type`` 1, 6, 5 and 8,
        respectively.
        """
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
        """
        The ``get_balance_by_date`` function should return the ``Accounts``
        balance at the end of the ``date`` if there are ``Transactions`` on
        previous days but not on the input ``date``.
        """
        date = datetime.date.today() - datetime.timedelta(days=1)
        entry = create_entry(date, 'entry')
        create_transaction(entry, self.child_acc, 20)
        create_transaction(entry, self.child_acc, 20)
        self.assertEqual(self.child_acc.get_balance_by_date(datetime.date.today()), 40)

    def test_get_balance_by_date_previous_transactions_starting_balance(self):
        """
        The ``get_balance_by_date`` method should return a Decimal value of the
        starting balance if the ``Account`` has ``Transactions`` only before
        the ``date``.

        Fix for bug#167
        """
        today = datetime.date.today()
        date = today - datetime.timedelta(days=1)
        account_w_balance = create_account('test acc', self.child_head, 42)
        entry = create_entry(date, 'entry')
        create_transaction(entry, account_w_balance, 20)
        create_transaction(entry, account_w_balance, 20)
        account_w_balance = Account.objects.get(id=account_w_balance.id)
        self.assertEqual(account_w_balance.get_balance_by_date(today), 82)

    def test_get_balance_by_date_future_transactions(self):
        """
        The ``get_balance_by_date`` method should return a Decimal value of 0
        if the ``Account`` has ``Transactions`` only after the ``date``.
        """
        date = datetime.date.today() + datetime.timedelta(days=1)
        entry = create_entry(date, 'entry')
        create_transaction(entry, self.child_acc, 20)
        create_transaction(entry, self.child_acc, 20)
        self.child_acc = Account.objects.get(id=self.child_acc.id)
        self.assertEqual(self.child_acc.get_balance_by_date(datetime.date.today()), 0)

    def test_get_balance_by_date_future_transactions_starting_balance(self):
        """
        The ``get_balance_by_date`` method should return a Decimal value of the
        starting balance if the ``Account`` has ``Transactions`` only after the
        ``date``.

        Fix for bug#167
        """
        today = datetime.date.today()
        date = today + datetime.timedelta(days=1)
        account_w_balance = create_account('test acc', self.child_head, 42)
        entry = create_entry(date, 'entry')
        create_transaction(entry, account_w_balance, 20)
        create_transaction(entry, account_w_balance, 20)
        account_w_balance = Account.objects.get(id=account_w_balance.id)
        self.assertEqual(account_w_balance.get_balance_by_date(today), 42)

    def test_get_balance_by_date_no_transactions(self):
        """
        The ``get_balance_by_date`` method should return a Decimal value of 0
        if the ``Account`` has no ``Transactions``.
        """
        date = datetime.date.today()
        balance = self.child_acc.get_balance_by_date(date=date)
        self.assertTrue(isinstance(balance, Decimal))
        self.assertEqual(balance, 0)

    def test_get_balance_by_date_no_transactions_starting_balance(self):
        """
        The ``get_balance_by_date`` method should return a Decimal value of the
        starting balance if the ``Account`` has no ``Transactions``

        Fix for bug#167
        """
        date = datetime.date.today()
        account_w_balance = create_account('test acc', self.child_head, 42)
        self.assertEqual(account_w_balance.get_balance_by_date(date), 42)

    def test_get_balance_by_date_multiple_transactions(self):
        """
        The ``get_balance_by_date`` function should return the ``Accounts``
        balance at the end of the ``date`` if there are multiple
        ``Transactions`` on the ``date``.
        """
        date = datetime.date.today()
        entry = create_entry(date, 'entry')
        create_transaction(entry, self.child_acc, 20)
        create_transaction(entry, self.child_acc, 20)
        self.assertEqual(self.child_acc.get_balance_by_date(date), 40)

    def test_get_balance_by_date_previous_and_current_transactions(self):
        """
        The ``get_balance_by_date`` function should return the ``Accounts``
        balance at the end of the ``date`` if there are ``Transactions`` on
        previous days and on the input ``date``.
        """
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
        """
        The ``get_balance_by_date`` function should return the ``Accounts``
        balance at the end of the ``date`` if there are ``Transactions`` on
        future days and on the input ``date``.
        """
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
        """
        The ``get_balance_by_date`` function should return the ``Accounts``
        balance at the end of the ``date`` if there are ``Transactions`` on
        previous days and after the input ``date``, but not on it.
        """
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
        """
        The ``get_balance_by_date`` function should return the ``Accounts``
        balance at the end of the ``date`` if there are ``Transactions`` on
        previous and future days and on the input ``date``.
        """
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
        """
        The ``get_balance_change_by_month`` method should return the
        ``Accounts`` net change for the designated ``month`` if there is a
        ``Transaction`` in the ``month``.
        """
        today = datetime.date.today()
        entry = create_entry(today, 'today entry')
        create_transaction(entry, self.child_acc, 20)
        self.assertEqual(self.child_acc.get_balance_change_by_month(today), 20)

    def test_get_balance_change_by_month_flipped(self):
        """
        The ``get_balance_change_by_month`` method should a flipped
        net_change for ``Accounts`` that are Assets, Expenses, Cost of Sales
        or Other Expenses (``type`` 1, 6, 5, 8 respectively).
        """
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
        """
        The ``get_balance_change_by_month`` method should return the
        ``Accounts`` net balance change for the desingated ``month`` if there
        are multiple ``Transactions`` in the ``month``.
        """
        today = datetime.date.today()
        entry = create_entry(today, 'today entry')
        create_transaction(entry, self.child_acc, 20)
        create_transaction(entry, self.child_acc, 20)
        self.assertEqual(self.child_acc.get_balance_change_by_month(today), 40)

    def test_get_balance_change_by_month_previous_transactions(self):
        """
        The ``get_balance_change_by_month`` method should return a ``Decimal``
        with a value of ``0`` if there are ``Transactions`` in previous months
        but not in the ``date`` input.
        """
        today = datetime.date.today()
        months_ago = today - datetime.timedelta(days=60)
        entry = create_entry(months_ago, 'past entry')
        create_transaction(entry, self.child_acc, 20)
        create_transaction(entry, self.child_acc, 20)
        self.assertEqual(self.child_acc.get_balance_change_by_month(today), 0)

    def test_get_balance_change_by_month_prev_and_curr_transactions(self):
        """
        The ``get_balance_change_by_month`` method should return the
        ``Accounts`` correct net balance change for the desingated ``month``
        if there are multiple ``Transactions`` in the ``month`` and in months
        before.
        """
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
        """
        The ``get_balance_change_by_month`` method should return a ``Decimal``
        with a value of ``0`` if there are ``Transactions`` in future months
        but not in the ``date`` input.
        """
        today = datetime.date.today()
        future_month = today + datetime.timedelta(days=60)
        entry = create_entry(future_month, 'future entry')
        create_transaction(entry, self.child_acc, 20)
        create_transaction(entry, self.child_acc, 20)
        self.assertEqual(self.child_acc.get_balance_change_by_month(today), 0)

    def test_get_balance_change_by_month_future_and_curr_transactions(self):
        """
        The ``get_balance_change_by_month`` method should return the
        ``Accounts`` correct net balance change for the desingated ``month``
        if there are multiple ``Transactions`` in the ``month`` and in future
        months.
        """
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
        """
        The ``get_balance_change_by_month`` method should return the
        ``Accounts`` correct net balance change for the desingated ``month``
        if there are multiple ``Transactions`` in the ``month`` and in future
        and past months.
        """
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
        """
        The ``get_balance_change_by_month`` method should return a ``Decimal``
        with a value of ``0`` if the account has no ``Transactions``.
        """
        date = datetime.date.today()
        net_change = self.child_acc.get_balance_change_by_month(date=date)
        self.assertTrue(isinstance(net_change, Decimal))
        self.assertEqual(net_change, 0)

    def test_current_earnings_get_balance(self):
        """
        For the Current Year Earnings Account, the `get_balance` method will
        return the sum of all balance_deltas of Accounts with `type` 4-8.
        """
        equity_header = create_header('Equity', cat_type=3)
        current_earnings = create_account('Current Year Earnings', equity_header, 0, 3)
        income_header = create_header('Income', None, 4)
        income_account = create_account('Income', income_header, 0, 4)
        cost_header = create_header('Cost of Sales', None, 5)
        cost_account = create_account('Cost of Sales', cost_header, 0, 5)
        expense_header = create_header('Expense', None, 6)
        expense_account = create_account('Expense', expense_header, 0, 6)
        oth_income_header = create_header('Other Income', None, 7)
        oth_income = create_account('Other Income', oth_income_header, 0, 7)
        oth_expense_header = create_header('Other Expense', None, 8)
        oth_expense = create_account('Other Expense', oth_expense_header, 0, 8)

        entry = create_entry(datetime.date.today(), 'test entry')
        create_transaction(entry, income_account, -35)
        create_transaction(entry, cost_account, 420)
        create_transaction(entry, expense_account, 67)
        create_transaction(entry, oth_income, -89)
        create_transaction(entry, oth_expense, 44)

        self.assertEqual(current_earnings.get_balance(), 407)

    def test_current_earnings_get_balance_by_date(self):
        """
        For the Current Year Earnings Account, the `get_balance_by_date` method
        will return the sum of all Account balances with `type` 4-8 on the
        specified date.
        """
        equity_header = create_header('Equity', cat_type=3)
        current_earnings = create_account('Current Year Earnings', equity_header, 0, 3)
        income_header = create_header('Income', None, 4)
        income_account = create_account('Income', income_header, 0, 4)
        cost_header = create_header('Cost of Sales', None, 5)
        cost_account = create_account('Cost of Sales', cost_header, 0, 5)
        expense_header = create_header('Expense', None, 6)
        expense_account = create_account('Expense', expense_header, 0, 6)
        oth_income_header = create_header('Other Income', None, 7)
        oth_income = create_account('Other Income', oth_income_header, 0, 7)
        oth_expense_header = create_header('Other Expense', None, 8)
        oth_expense = create_account('Other Expense', oth_expense_header, 0, 8)

        today = datetime.date.today()
        past = today - datetime.timedelta(days=20)
        entry = create_entry(past, 'past entry')
        create_transaction(entry, income_account, -35)
        create_transaction(entry, cost_account, 420)
        create_transaction(entry, expense_account, 67)
        create_transaction(entry, oth_income, -89)
        create_transaction(entry, oth_expense, 44)
        entry = create_entry(today, 'today entry')
        create_transaction(entry, income_account, -35)
        create_transaction(entry, cost_account, 420)
        create_transaction(entry, expense_account, 67)
        create_transaction(entry, oth_income, -89)
        create_transaction(entry, oth_expense, 44)

        self.assertEqual(current_earnings.get_balance_by_date(past), 407)
        self.assertEqual(current_earnings.get_balance_by_date(today), 814)

    def test_current_earnings_get_balance_change_by_month(self):
        """
        For the Current Year Earnngs Account, the `get_balance_change_by_month`
        method will return the sum of all balance_deltas for all Accounts of
        `type` 4-8 in the speicifed month.
        """
        equity_header = create_header('Equity', cat_type=3)
        current_earnings = create_account('Current Year Earnings', equity_header, 0, 3)
        income_header = create_header('Income', None, 4)
        income_account = create_account('Income', income_header, 0, 4)
        cost_header = create_header('Cost of Sales', None, 5)
        cost_account = create_account('Cost of Sales', cost_header, 0, 5)
        expense_header = create_header('Expense', None, 6)
        expense_account = create_account('Expense', expense_header, 0, 6)
        oth_income_header = create_header('Other Income', None, 7)
        oth_income = create_account('Other Income', oth_income_header, 0, 7)
        oth_expense_header = create_header('Other Expense', None, 8)
        oth_expense = create_account('Other Expense', oth_expense_header, 0, 8)

        today = datetime.date.today()
        past = today - datetime.timedelta(days=60)
        entry = create_entry(past, 'past entry')
        create_transaction(entry, income_account, 35)
        create_transaction(entry, cost_account, 420)
        create_transaction(entry, expense_account, 67)
        create_transaction(entry, oth_income, 89)
        create_transaction(entry, oth_expense, 44)
        entry = create_entry(today, 'today entry')
        create_transaction(entry, income_account, -35)
        create_transaction(entry, cost_account, 420)
        create_transaction(entry, expense_account, 67)
        create_transaction(entry, oth_income, -89)
        create_transaction(entry, oth_expense, 44)

        self.assertEqual(current_earnings.get_balance_change_by_month(past), 655)
        self.assertEqual(current_earnings.get_balance_change_by_month(today), 407)

    def test_account_delete_no_transactions(self):
        """
        Accounts can be deleted if they have no Transactions.
        """
        self.assertEqual(Account.objects.count(), 2)
        self.child_acc.delete()
        self.assertEqual(Account.objects.count(), 1)

    def test_account_delete_with_transactions(self):
        """
        Accounts can not be deleted if they have Transactions.
        """
        entry = create_entry(datetime.date.today(), 'blocking entry')
        create_transaction(entry, self.child_acc, 20)
        self.assertEqual(Account.objects.count(), 2)
        self.assertRaises(ProtectedError, self.child_acc.delete)


class HistoricalAccountModelTests(TestCase):
    """Tests the custom methods on the ``HistoricalAccount`` model."""
    def setUp(self):
        today = datetime.date.today()
        self.liability_historical = HistoricalAccount.objects.create(
            number='2-1001', name='Test Liability', type=2,
            amount=Decimal('-900.25'),
            date=datetime.date(day=1,
                               month=today.month,
                               year=(today.year - 1)))
        self.asset_historical = HistoricalAccount.objects.create(
            number='1-1001', name='Test Asset', type=1,
            amount=Decimal('-9000.01'),
            date=datetime.date(day=1,
                               month=today.month,
                               year=(today.year - 1)))

    def test_get_amount(self):
        """
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
        """
        self.assertEqual(self.liability_historical.get_amount(),
                         Decimal('-900.25'))
        self.assertEqual(self.asset_historical.get_amount(),
                         Decimal('9000.01'))

    def test_flip_balance(self):
        """
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
        """
        today = datetime.date.today()
        equity_historical = HistoricalAccount.objects.create(
            number='3-1001', name='Test Equity', type=3, amount=Decimal('4'),
            date=today)
        income_historical = HistoricalAccount.objects.create(
            number='4-1001', name='Test Income', type=4, amount=Decimal('2'),
            date=today)
        cost_sale_historical = HistoricalAccount.objects.create(
            number='5-1001', name='Test CoS', type=5, amount=Decimal('0'),
            date=today)
        expense_historical = HistoricalAccount.objects.create(
            number='6-1001', name='Test Expense', type=6, amount=Decimal('4'),
            date=today)
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


class AccountManagerTests(TestCase):
    """Test the manager class for the Account object."""
    def test_banks(self):
        """The method should return all banks if any exist."""
        header = create_header('Initial')
        bank1 = create_account('Bank Account 1', header, 0, bank=True)
        create_account('Not a bank', header, 0)
        bank2 = create_account('Bank Account 2', header, 0, bank=True)

        result = Account.objects.get_banks()

        self.assertSequenceEqual([bank1, bank2], result)

    def test_banks_no_bank(self):
        """The method should return an empty list if no banks exist."""
        result = Account.objects.get_banks()
        self.assertSequenceEqual([], result)

    def test_active(self):
        """The method should all Accounts marked active."""
        header = create_header('Initial')
        active1 = create_account('Active 1', header, 0)
        active2 = create_account('Active 2', header, 0)
        inactive = create_account('Inactive', header, 0)
        inactive.active = False
        inactive.save()

        active = Account.objects.active()

        self.assertSequenceEqual([active1, active2], active)

    def test_active_none_active(self):
        """The method should return an empty list if no accounts are active."""
        header = create_header('Initial')
        inactive = create_account('Inactive', header, 0)
        inactive.active = False
        inactive.save()

        active = Account.objects.active()

        self.assertSequenceEqual([], active)


class QuickSearchViewTests(TestCase):
    """
    Test views for redirecting dropdowns to Account details or a Bank Account's
    journal
    """
    def setUp(self):
        """
        An Account and Bank Account are required the respective searches
        """
        self.asset_header = create_header('asset', cat_type=1)
        self.liability_header = create_header('liability', cat_type=2)
        self.bank_account = create_account('bank', self.asset_header, 0, 1, True)
        self.liability_account = create_account('liability', self.liability_header, 0, 2)

    def test_quick_account_success(self):
        """
        A `GET` to the `quick_account_search` view with an `account` should
        redirect to the Account's detail page.
        """
        response = self.client.get(
            reverse('accounts.views.quick_account_search'),
            data={'account': self.liability_account.id}
        )

        self.assertRedirects(response,
                             reverse('accounts.views.show_account_detail',
                                     args=[self.liability_account.slug]))

    def test_quick_account_fail_not_account(self):
        """
        A `GET` to the `quick_account_search` view with an `account` should
        return a 404 if the Account does not exist.
        """
        response = self.client.get(reverse('accounts.views.quick_account_search'),
                                   data={'account': 9001})

        self.assertEqual(response.status_code, 404)

    def test_quick_account_fail_no_account(self):
        """
        A `GET` to the `quick_account_search` view with no `account` should
        return a 404.
        """
        response = self.client.get(reverse('accounts.views.quick_account_search'))
        self.assertEqual(response.status_code, 404)

    def test_quick_bank_success(self):
        """
        A `GET` to the `quick_bank_search` view with a `bank` should
        redirect to the Account's journal page.
        """
        response = self.client.get(reverse('accounts.views.quick_bank_search'),
                                   data={'bank': self.bank_account.id})

        self.assertRedirects(response, reverse('accounts.views.bank_journal', args=[self.bank_account.slug]))

    def test_quick_bank_fail_not_bank(self):
        """
        A `GET` to the `quick_bank_search` view with a `bank` should
        return a 404 if the Account is not a bank.
        """
        response = self.client.get(reverse('accounts.views.quick_bank_search'),
                                   data={'bank': self.liability_account.id})

        self.assertEqual(response.status_code, 404)

    def test_quick_bank_fail_not_account(self):
        """
        A `GET` to the `quick_bank_search` view with a `bank` should
        return a 404 if the Account does not exist.
        """
        response = self.client.get(reverse('accounts.views.quick_bank_search'),
                                   data={'bank': 9001})

        self.assertEqual(response.status_code, 404)

    def test_quick_bank_fail_no_bank(self):
        """
        A `GET` to the `quick_bank_search` view with no `bank` should return
        a 404.
        """
        response = self.client.get(reverse('accounts.views.quick_bank_search'))
        self.assertEqual(response.status_code, 404)


class AccountChartViewTests(TestCase):
    """
    Test Account Chart display and Header child displays
    """
    def setUp(self):
        self.asset_header = create_header('asset', cat_type=1)
        self.asset_child_header = create_header('asset child', parent=self.asset_header, cat_type=1)
        self.expense_header = create_header('expense', cat_type=6)
        self.expense_child_header = create_header('expense child', parent=self.expense_header, cat_type=6)

    def test_show_chart_initial(self):
        """
        A `GET` to the `show_accounts_chart` view should return the Header tree.
        """
        response = self.client.get(reverse('accounts.views.show_accounts_chart'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/account_charts.html')
        self.assertNotIn('header', response.context)
        self.assertSequenceEqual(response.context['root_nodes'],
                                 [self.asset_header, self.expense_header])
        self.assertSequenceEqual(response.context['root_nodes'][0].descendants,
                                 [self.asset_header, self.asset_child_header])
        self.assertSequenceEqual(
            response.context['root_nodes'][1].descendants,
            [self.expense_header, self.expense_child_header])

    def test_show_chart_header_success(self):
        """
        A `GET` to the `show_accounts_chart` view with a `header_slug` should
        retrieve the Header and it's children.
        """
        response = self.client.get(
            reverse('accounts.views.show_accounts_chart',
                    kwargs={'header_slug': self.asset_header.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['header'], self.asset_header)
        self.assertSequenceEqual(response.context['root_nodes'],
                                 [self.asset_header])
        self.assertEqual(len(response.context['root_nodes']), 1)
        self.assertSequenceEqual(response.context['root_nodes'][0].descendants,
                                 [self.asset_header, self.asset_child_header])

    def test_show_chart_header_fail(self):
        """
        A `GET` to the `show_accounts_chart` view with an invalid `header_slug`
        should return a 404.
        """
        response = self.client.get(
            reverse('accounts.views.show_accounts_chart',
                    kwargs={'header_slug': 'does-not-exist'}))
        self.assertEqual(response.status_code, 404)


class AccountReconcileViewTests(TestCase):
    """
    Test the `reconcile_account` view
    """
    def setUp(self):
        """
        Test Accounts with `flip_balance` of `True`(asset/bank) and `False`(liability).
        """
        self.asset_header = create_header('asset', cat_type=1)
        self.liability_header = create_header('liability', cat_type=2)
        self.bank_account = create_account('bank', self.asset_header, 0, 1, True)
        self.liability_account = create_account('liability', self.liability_header, 0, 2)

    def test_reconcile_account_view_initial(self):
        """
        A `GET` to the `reconcile_account` view with an `account_slug` should
        return an AccountReconcile Form for that Account.
        """
        response = self.client.get(
            reverse('accounts.views.reconcile_account',
                    kwargs={'account_slug': self.bank_account.slug}))

        self.assertEqual(response.status_code, 200)
        self.failUnless(isinstance(response.context['account_form'],
                                   AccountReconcileForm))
        self.assertNotIn('transaction_formset', response.context)
        self.assertTemplateUsed(response, 'accounts/account_reconcile.html')
        self.assertEqual(response.context['account'], self.bank_account)
        self.assertEqual(response.context['last_reconciled'],
                         self.bank_account.last_reconciled)
        self.assertEqual(response.context['reconciled_balance'], 0)

    def test_reconcile_account_initial_statement_balance_no_reconciled(self):
        """
        The initial view will display a Statement Balance of 0 if no reconciled
        Transactions exist.
        """
        response = self.client.get(
            reverse('accounts.views.reconcile_account',
                    kwargs={'account_slug': self.bank_account.slug}))

        account_form = response.context['account_form']
        self.assertEqual(account_form.initial['statement_balance'], 0)

    def test_reconcile_account_initial_statement_balance_reconciled(self):
        """
        The initial view will display a Statement Balance of the reconciled
        amount if previously reconciled Transactions exist.
        """
        self.test_reconcile_account_view_flip_success_pos_statement_zero_reconciled()

        response = self.client.get(
            reverse('accounts.views.reconcile_account',
                    kwargs={'account_slug': self.bank_account.slug}))

        account_form = response.context['account_form']
        self.assertEqual(account_form.initial['statement_balance'], 275)

    def test_reconcile_account_view_initial_account_slug_fail(self):
        """ A `GET` to the `reconcile_account` view with an invalid
        `account_slug` should return a 404.  """
        response = self.client.get(
            reverse('accounts.views.reconcile_account',
                    kwargs={'account_slug': 'I-dont-exist'}))
        self.assertEqual(response.status_code, 404)

    def test_reconcile_account_view_initial_post_account_slug_fail(self):
        """
        A `POST` to the `reconcile_account` view with an invalid `account_slug`
        should return a 404.
        """
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': 'I-dont-exist'}))
        self.assertEqual(response.status_code, 404)

    def test_reconcile_account_view_get_transactions(self):
        """
        A `POST` to the `reconcile_account` view with a `statement_date`,
        `statement_balance` and submit value of `Get Transactions` should return
        the bound AccountReconcile Form and a ReconcileTransactionFormSet containing
        the Account's unreconciled Transactions from between the Account's
        `last_reconciled` date and the `statement_date`.
        """
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
        """
        A `POST` to the `reconcile_account` view with a `statement_date` before
        the Accounts last_reconciled date will return an Error and no Transactions.
        """
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
        self.assertFormError(response, 'account_form', 'statement_date', 'The Statement Date must be later than the Last Reconciled Date.')
        self.assertNotIn('transaction_formset', response.context)

    def test_reconcile_account_view_flip_success_neg_statement_zero_reconciled(self):
        """
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of True, `statement_amount` < 0  and
        a `reconciled_amount` of 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        """
        entry = create_entry(datetime.date.today(), 'test memo')
        trans1 = create_transaction(entry, self.bank_account, -50)
        trans2 = create_transaction(entry, self.bank_account, -50)
        trans3 = create_transaction(entry, self.bank_account, 275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=5),
                                          'account-statement_balance': '-175',
                                          'form-TOTAL_FORMS': 3,
                                          'form-INITIAL_FORMS': 3,
                                          'form-0-id': trans1.id,
                                          'form-0-reconciled': True,
                                          'form-1-id': trans2.id,
                                          'form-1-reconciled': True,
                                          'form-2-id': trans3.id,
                                          'form-2-reconciled': True,
                                          'submit': 'Reconcile Transactions'})
        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.bank_account.slug}))
        self.assertTrue(Transaction.objects.all()[0].reconciled)
        self.assertTrue(Transaction.objects.all()[1].reconciled)
        self.assertTrue(Transaction.objects.all()[2].reconciled)

    def test_reconcile_account_view_flip_success_zero_statement_zero_reconciled(self):
        """
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of True, `statement_amount` of 0  and
        a `reconciled_amount` of 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        """
        entry = create_entry(datetime.date.today(), 'test memo')
        trans1 = create_transaction(entry, self.bank_account, -50)
        trans2 = create_transaction(entry, self.bank_account, 50)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=5),
                                          'account-statement_balance': '0',
                                          'form-TOTAL_FORMS': 2,
                                          'form-INITIAL_FORMS': 2,
                                          'form-0-id': trans1.id,
                                          'form-0-reconciled': True,
                                          'form-1-id': trans2.id,
                                          'form-1-reconciled': True,
                                          'submit': 'Reconcile Transactions'})

        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.bank_account.slug}))
        self.assertTrue(Transaction.objects.all()[0].reconciled)
        self.assertTrue(Transaction.objects.all()[1].reconciled)

    def test_reconcile_account_view_flip_success_pos_statement_zero_reconciled(self):
        """
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of True, `statement_amount` > 0  and
        a `reconciled_amount` of 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        """
        entry = create_entry(datetime.date.today(), 'test memo')
        trans1 = create_transaction(entry, self.bank_account, -275)
        create_transaction(entry, self.liability_account, 275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=5),
                                          'account-statement_balance': '275',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': trans1.id,
                                          'form-0-reconciled': True,
                                          'submit': 'Reconcile Transactions'})

        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.bank_account.slug}))
        self.assertTrue(Transaction.objects.all()[0].reconciled)
        self.assertFalse(Transaction.objects.all()[1].reconciled)

    def test_reconcile_account_view_flip_success_neg_statement_neg_reconciled(self):
        """
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of True, `statement_amount` < 0  and
        a `reconciled_balance` < 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        """
        self.test_reconcile_account_view_flip_success_neg_statement_zero_reconciled()
        entry = create_entry(datetime.date.today() + datetime.timedelta(days=7), 'test memo')
        trans1 = create_transaction(entry, self.bank_account, 275)
        create_transaction(entry, self.liability_account, -275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=10),
                                          'account-statement_balance': '-450',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': trans1.id,
                                          'form-0-reconciled': True,
                                          'submit': 'Reconcile Transactions'})
        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.bank_account.slug}))
        self.assertTrue(Transaction.objects.all()[3].reconciled)
        self.assertFalse(Transaction.objects.all()[4].reconciled)

    def test_reconcile_account_view_flip_success_pos_statement_neg_reconciled(self):
        """
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of True, `statement_amount` > 0  and
        a `reconciled_balance` < 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        """
        self.test_reconcile_account_view_flip_success_neg_statement_zero_reconciled()
        entry = create_entry(datetime.date.today() + datetime.timedelta(days=7), 'test memo')
        trans1 = create_transaction(entry, self.bank_account, -275)
        create_transaction(entry, self.liability_account, 275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=10),
                                          'account-statement_balance': '100',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': trans1.id,
                                          'form-0-reconciled': True,
                                          'submit': 'Reconcile Transactions'})
        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.bank_account.slug}))
        self.assertTrue(Transaction.objects.all()[3].reconciled)
        self.assertFalse(Transaction.objects.all()[4].reconciled)

    def test_reconcile_account_view_flip_success_zero_statement_neg_reconciled(self):
        """
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of True, `statement_amount` of 0  and
        a `reconciled_balance` < 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        """
        self.test_reconcile_account_view_flip_success_neg_statement_zero_reconciled()
        entry = create_entry(datetime.date.today() + datetime.timedelta(days=7), 'test memo')
        trans1 = create_transaction(entry, self.bank_account, -175)
        create_transaction(entry, self.liability_account, 275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=10),
                                          'account-statement_balance': '0',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': trans1.id,
                                          'form-0-reconciled': True,
                                          'submit': 'Reconcile Transactions'})
        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.bank_account.slug}))
        self.assertTrue(Transaction.objects.all()[3].reconciled)
        self.assertFalse(Transaction.objects.all()[4].reconciled)

    def test_reconcile_account_view_flip_success_neg_statement_pos_reconciled(self):
        """
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of True, `statement_amount` < 0  and
        a `reconciled_balance` < 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        """
        self.test_reconcile_account_view_flip_success_pos_statement_zero_reconciled()
        entry = create_entry(datetime.date.today() + datetime.timedelta(days=7), 'test memo')
        trans1 = create_transaction(entry, self.bank_account, 375)
        create_transaction(entry, self.liability_account, -275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=10),
                                          'account-statement_balance': '-100',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': trans1.id,
                                          'form-0-reconciled': True,
                                          'submit': 'Reconcile Transactions'})
        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.bank_account.slug}))
        self.assertTrue(Transaction.objects.all()[2].reconciled)
        self.assertFalse(Transaction.objects.all()[3].reconciled)

    def test_reconcile_account_view_flip_success_pos_statement_pos_reconciled(self):
        """
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of True, `statement_amount` > 0  and
        a `reconciled_balance` < 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        """
        self.test_reconcile_account_view_flip_success_pos_statement_zero_reconciled()
        entry = create_entry(datetime.date.today() + datetime.timedelta(days=7), 'test memo')
        trans1 = create_transaction(entry, self.bank_account, 175)
        create_transaction(entry, self.liability_account, 275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=10),
                                          'account-statement_balance': '100',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': trans1.id,
                                          'form-0-reconciled': True,
                                          'submit': 'Reconcile Transactions'})
        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.bank_account.slug}))
        self.assertTrue(Transaction.objects.all()[2].reconciled)
        self.assertFalse(Transaction.objects.all()[3].reconciled)

    def test_reconcile_account_view_flip_success_zero_statement_pos_reconciled(self):
        """
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of True, `statement_amount` of 0  and
        a `reconciled_balance` < 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        """
        self.test_reconcile_account_view_flip_success_neg_statement_zero_reconciled()
        entry = create_entry(datetime.date.today() + datetime.timedelta(days=7), 'test memo')
        trans1 = create_transaction(entry, self.bank_account, -175)
        create_transaction(entry, self.liability_account, 275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=10),
                                          'account-statement_balance': '0',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': trans1.id,
                                          'form-0-reconciled': True,
                                          'submit': 'Reconcile Transactions'})
        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.bank_account.slug}))
        self.assertTrue(Transaction.objects.all()[3].reconciled)
        self.assertFalse(Transaction.objects.all()[4].reconciled)

    def test_reconcile_account_view_no_flip_success_neg_statement_zero_reconciled(self):
        """
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of False, `statement_amount` < 0  and
        a `reconciled_amount` of 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        """
        entry = create_entry(datetime.date.today(), 'test memo')
        trans1 = create_transaction(entry, self.liability_account, 50)
        trans2 = create_transaction(entry, self.liability_account, 50)
        trans3 = create_transaction(entry, self.liability_account, -275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.liability_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=5),
                                          'account-statement_balance': '-175',
                                          'form-TOTAL_FORMS': 3,
                                          'form-INITIAL_FORMS': 3,
                                          'form-0-id': trans1.id,
                                          'form-0-reconciled': True,
                                          'form-1-id': trans2.id,
                                          'form-1-reconciled': True,
                                          'form-2-id': trans3.id,
                                          'form-2-reconciled': True,
                                          'submit': 'Reconcile Transactions'})

        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.liability_account.slug}))
        self.assertTrue(Transaction.objects.all()[0].reconciled)
        self.assertTrue(Transaction.objects.all()[1].reconciled)
        self.assertTrue(Transaction.objects.all()[2].reconciled)

    def test_reconcile_account_view_no_flip_success_zero_statement_zero_reconciled(self):
        """
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of False, `statement_amount` of 0  and
        a `reconciled_amount` of 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        """
        entry = create_entry(datetime.date.today(), 'test memo')
        trans1 = create_transaction(entry, self.liability_account, -50)
        trans2 = create_transaction(entry, self.liability_account, 50)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.liability_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=5),
                                          'account-statement_balance': '0',
                                          'form-TOTAL_FORMS': 2,
                                          'form-INITIAL_FORMS': 2,
                                          'form-0-id': trans1.id,
                                          'form-0-reconciled': True,
                                          'form-1-id': trans2.id,
                                          'form-1-reconciled': True,
                                          'submit': 'Reconcile Transactions'})

        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.liability_account.slug}))
        self.assertTrue(Transaction.objects.all()[0].reconciled)
        self.assertTrue(Transaction.objects.all()[1].reconciled)

    def test_reconcile_account_view_no_flip_success_pos_statement_zero_reconciled(self):
        """
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of False, `statement_amount` > 0  and
        a `reconciled_amount` of 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        """
        entry = create_entry(datetime.date.today(), 'test memo')
        create_transaction(entry, self.bank_account, -275)
        trans2 = create_transaction(entry, self.liability_account, 275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.liability_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=5),
                                          'account-statement_balance': '275',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': trans2.id,
                                          'form-0-reconciled': True,
                                          'submit': 'Reconcile Transactions'})

        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.liability_account.slug}))
        self.assertTrue(Transaction.objects.all()[1].reconciled)
        self.assertFalse(Transaction.objects.all()[0].reconciled)

    def test_reconcile_account_view_no_flip_success_neg_statement_neg_reconciled(self):
        """
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of False, `statement_amount` < 0  and
        a `reconciled_balance` < 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        """
        self.test_reconcile_account_view_no_flip_success_neg_statement_zero_reconciled()
        entry = create_entry(datetime.date.today() + datetime.timedelta(days=7), 'test memo')
        create_transaction(entry, self.bank_account, 275)
        trans5 = create_transaction(entry, self.liability_account, -275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.liability_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=10),
                                          'account-statement_balance': '-450',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': trans5.id,
                                          'form-0-reconciled': True,
                                          'submit': 'Reconcile Transactions'})
        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.liability_account.slug}))
        self.assertTrue(Transaction.objects.all()[4].reconciled)
        self.assertFalse(Transaction.objects.all()[3].reconciled)

    def test_reconcile_account_view_no_flip_success_pos_statement_neg_reconciled(self):
        """
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of False, `statement_amount` > 0  and
        a `reconciled_balance` < 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        """
        self.test_reconcile_account_view_no_flip_success_neg_statement_zero_reconciled()
        entry = create_entry(datetime.date.today() + datetime.timedelta(days=7), 'test memo')
        create_transaction(entry, self.bank_account, -275)
        trans5 = create_transaction(entry, self.liability_account, 275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.liability_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=10),
                                          'account-statement_balance': '100',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': trans5.id,
                                          'form-0-reconciled': True,
                                          'submit': 'Reconcile Transactions'})
        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.liability_account.slug}))
        self.assertTrue(Transaction.objects.all()[4].reconciled)
        self.assertFalse(Transaction.objects.all()[3].reconciled)

    def test_reconcile_account_view_no_flip_success_zero_statement_neg_reconciled(self):
        """
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of False, `statement_amount` of 0  and
        a `reconciled_balance` < 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        """
        self.test_reconcile_account_view_no_flip_success_neg_statement_zero_reconciled()
        entry = create_entry(datetime.date.today() + datetime.timedelta(days=7), 'test memo')
        create_transaction(entry, self.bank_account, -175)
        trans5 = create_transaction(entry, self.liability_account, 175)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.liability_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=10),
                                          'account-statement_balance': '0',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': trans5.id,
                                          'form-0-reconciled': True,
                                          'submit': 'Reconcile Transactions'})
        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.liability_account.slug}))
        self.assertTrue(Transaction.objects.all()[4].reconciled)
        self.assertFalse(Transaction.objects.all()[3].reconciled)

    def test_reconcile_account_view_no_flip_success_neg_statement_pos_reconciled(self):
        """
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of False, `statement_amount` < 0  and
        a `reconciled_balance` < 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        """
        self.test_reconcile_account_view_no_flip_success_pos_statement_zero_reconciled()
        entry = create_entry(datetime.date.today() + datetime.timedelta(days=7), 'test memo')
        create_transaction(entry, self.bank_account, 375)
        trans4 = create_transaction(entry, self.liability_account, -375)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.liability_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=10),
                                          'account-statement_balance': '-100',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': trans4.id,
                                          'form-0-reconciled': True,
                                          'submit': 'Reconcile Transactions'})
        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.liability_account.slug}))
        self.assertTrue(Transaction.objects.all()[3].reconciled)
        self.assertFalse(Transaction.objects.all()[2].reconciled)

    def test_reconcile_account_view_no_flip_success_pos_statement_pos_reconciled(self):
        """
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of False, `statement_amount` > 0  and
        a `reconciled_balance` < 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        """
        self.test_reconcile_account_view_no_flip_success_pos_statement_zero_reconciled()
        entry = create_entry(datetime.date.today() + datetime.timedelta(days=7), 'test memo')
        create_transaction(entry, self.bank_account, 275)
        trans4 = create_transaction(entry, self.liability_account, 275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.liability_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=10),
                                          'account-statement_balance': '550',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': trans4.id,
                                          'form-0-reconciled': True,
                                          'submit': 'Reconcile Transactions'})
        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.liability_account.slug}))
        self.assertTrue(Transaction.objects.all()[3].reconciled)
        self.assertFalse(Transaction.objects.all()[2].reconciled)

    def test_reconcile_account_view_no_flip_success_zero_statement_pos_reconciled(self):
        """
        A `POST` to the `reconcile_account` view with a valid ReconcileTransactionFormSet
        data for an Account with `flip_balance()` of False, `statement_amount` of 0  and
        a `reconciled_balance` < 0 will mark the Transactions as Reconciled and
        redirect to the Account Detail Page.
        """
        self.test_reconcile_account_view_no_flip_success_pos_statement_zero_reconciled()
        entry = create_entry(datetime.date.today() + datetime.timedelta(days=7), 'test memo')
        create_transaction(entry, self.bank_account, 275)
        trans4 = create_transaction(entry, self.liability_account, -275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.liability_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=10),
                                          'account-statement_balance': '0',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': trans4.id,
                                          'form-0-reconciled': True,
                                          'submit': 'Reconcile Transactions'})
        self.assertRedirects(response, reverse('accounts.views.show_account_detail',
                                               kwargs={'account_slug': self.liability_account.slug}))
        self.assertTrue(Transaction.objects.all()[3].reconciled)
        self.assertFalse(Transaction.objects.all()[2].reconciled)

    def test_reconcile_account_view_fail_invalid_form_data(self):
        """
        A `POST` to the `reconcile_account` view with an invalid data
        should return forms with errors.
        """
        entry = create_entry(datetime.date.today(), 'test memo')
        trans1 = create_transaction(entry, self.bank_account, -275)
        create_transaction(entry, self.liability_account, 275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=5),
                                          'account-statement_balance': 'arg',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': trans1.id,
                                          'form-0-reconciled': 'over 9000',
                                          'submit': 'Reconcile Transactions'})

        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'account_form', 'statement_balance',
                             'Enter a number.')

    def test_reconcile_account_view_fail_no_submit(self):
        """
        A `POST` to the `reconcile_account` view with no value for `submit` should
        return a 404.
        """
        entry = create_entry(datetime.date.today(), 'test memo')
        trans1 = create_transaction(entry, self.bank_account, -275)
        create_transaction(entry, self.liability_account, 275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=5),
                                          'account-statement_balance': '275',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': trans1.id,
                                          'form-0-reconciled': True})
        self.assertEqual(response.status_code, 404)

    def test_reconcile_account_view_fail_invalid_submit(self):
        """
        A `POST` to the `reconcile_account` view with an invalid `submit` value
        should return a 404.
        """
        entry = create_entry(datetime.date.today(), 'test memo')
        trans1 = create_transaction(entry, self.bank_account, -275)
        create_transaction(entry, self.liability_account, 275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today() + datetime.timedelta(days=5),
                                          'account-statement_balance': '275',
                                          'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': trans1.id,
                                          'form-0-reconciled': True,
                                          'submit': 'this button doesnt exist'})
        self.assertEqual(response.status_code, 404)

    def test_reconcile_account_view_fail_old_statement_date(self):
        """
        A `POST` to the `reconcile_account` view with valid Transaction data
        but a `statement_date` before the Accounts last_reconciled date will
        return an Error and the Transactions.
        """
        self.bank_account.last_reconciled = datetime.date.today()
        self.bank_account.save()
        entry = create_entry(datetime.date.today(), 'test memo')
        trans1 = create_transaction(entry, self.bank_account, -50)
        trans2 = create_transaction(entry, self.bank_account, -50)
        trans3 = create_transaction(entry, self.bank_account, 275)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today() - datetime.timedelta(days=500),
                                          'account-statement_balance': '-175',
                                          'form-TOTAL_FORMS': 3,
                                          'form-INITIAL_FORMS': 3,
                                          'form-0-id': trans1.id,
                                          'form-0-reconciled': True,
                                          'form-1-id': trans2.id,
                                          'form-1-reconciled': True,
                                          'form-2-id': trans3.id,
                                          'form-2-reconciled': True,
                                          'submit': 'Reconcile Transactions'})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'account_form', 'statement_date', 'The Statement Date must be later than the Last Reconciled Date.')
        self.assertIn('transaction_formset', response.context)

    def test_reconcile_account_view_fail_statement_out_of_balance_flip(self):
        """
        A `POST` to the `reconcile_account` view with an out of balance statement
        will not mark the Transactions as Reconciled and return an out of balance
        error for Accounts where `flip_balance` is `True`.
        """
        entry = create_entry(datetime.date.today(), 'test memo')
        trans1 = create_transaction(entry, self.bank_account, 50)
        trans2 = create_transaction(entry, self.bank_account, 50)
        create_transaction(entry, self.liability_account, -100)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today(),
                                          'account-statement_balance': '75',
                                          'form-TOTAL_FORMS': 2,
                                          'form-INITIAL_FORMS': 2,
                                          'form-0-id': trans1.id,
                                          'form-0-reconciled': True,
                                          'form-1-id': trans2.id,
                                          'form-1-reconciled': True,
                                          'submit': 'Reconcile Transactions'})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.all()[0].reconciled)
        self.assertFalse(Transaction.objects.all()[1].reconciled)
        self.assertEqual(response.context['transaction_formset'].non_form_errors()[0],
                         'The selected Transactions are out of balance with the Statement Amount.')

    def test_reconcile_account_view_fail_transaction_out_of_balance_flip(self):
        """
        A `POST` to the `reconcile_account` view with out of balance Transactions
        will not mark the Transactions as Reconciled and return an out of balance
        error for Accounts where `flip_balance` is `True`.
        """
        entry = create_entry(datetime.date.today(), 'test memo')
        trans1 = create_transaction(entry, self.bank_account, 50)
        trans2 = create_transaction(entry, self.bank_account, 50)
        create_transaction(entry, self.liability_account, -100)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}),
                                    data={'account-statement_date': datetime.date.today(),
                                          'account-statement_balance': '100',
                                          'form-TOTAL_FORMS': 2,
                                          'form-INITIAL_FORMS': 2,
                                          'form-0-id': trans1.id,
                                          'form-0-reconciled': True,
                                          'form-1-id': trans2.id,
                                          'form-1-reconciled': False,
                                          'submit': 'Reconcile Transactions'})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.all()[0].reconciled)
        self.assertFalse(Transaction.objects.all()[1].reconciled)
        self.assertEqual(response.context['transaction_formset'].non_form_errors()[0],
                         'The selected Transactions are out of balance with the Statement Amount.')

    def test_reconcile_account_view_fail_statement_out_of_balance_no_flip(self):
        """
        A `POST` to the `reconcile_account` view with an out of balance statement
        will not mark the Transactions as Reconciled and return an out of balance
        error.
        """
        entry = create_entry(datetime.date.today(), 'test memo')
        create_transaction(entry, self.bank_account, 50)
        create_transaction(entry, self.bank_account, 50)
        trans3 = create_transaction(entry, self.liability_account, -50)
        trans4 = create_transaction(entry, self.liability_account, -50)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.liability_account.slug}),
                                    data={'account-statement_date': datetime.date.today(),
                                          'account-statement_balance': '75',
                                          'form-TOTAL_FORMS': 2,
                                          'form-INITIAL_FORMS': 2,
                                          'form-0-id': trans3.id,
                                          'form-0-reconciled': True,
                                          'form-1-id': trans4.id,
                                          'form-1-reconciled': True,
                                          'submit': 'Reconcile Transactions'})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.all()[2].reconciled)
        self.assertFalse(Transaction.objects.all()[3].reconciled)
        self.assertEqual(response.context['transaction_formset'].non_form_errors()[0],
                         'The selected Transactions are out of balance with the Statement Amount.')

    def test_reconcile_account_view_fail_transaction_out_of_balance_no_flip(self):
        """
        A `POST` to the `reconcile_account` view with out of balance Transactions
        will not mark the Transactions as Reconciled and return an out of balance
        error.
        """
        entry = create_entry(datetime.date.today(), 'test memo')
        create_transaction(entry, self.bank_account, 50)
        create_transaction(entry, self.bank_account, 50)
        trans3 = create_transaction(entry, self.liability_account, -50)
        trans4 = create_transaction(entry, self.liability_account, -50)
        response = self.client.post(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.liability_account.slug}),
                                    data={'account-statement_date': datetime.date.today(),
                                          'account-statement_balance': '100',
                                          'form-TOTAL_FORMS': 2,
                                          'form-INITIAL_FORMS': 2,
                                          'form-0-id': trans3.id,
                                          'form-0-reconciled': True,
                                          'form-1-id': trans4.id,
                                          'form-1-reconciled': False,
                                          'submit': 'Reconcile Transactions'})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.all()[2].reconciled)
        self.assertFalse(Transaction.objects.all()[3].reconciled)
        self.assertEqual(response.context['transaction_formset'].non_form_errors()[0],
                         'The selected Transactions are out of balance with the Statement Amount.')

    def test_reconcile_account_view_change_last_reconciled_date(self):
        """
        A successful Reconciliation should cause the `last_reconciled` and `reconciled_balance`
        variables to change
        """
        self.test_reconcile_account_view_flip_success_neg_statement_zero_reconciled()
        response = self.client.get(reverse('accounts.views.reconcile_account', kwargs={'account_slug': self.bank_account.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['last_reconciled'], datetime.date.today() + datetime.timedelta(days=5))
        self.assertEqual(Account.objects.get(bank=True).last_reconciled, datetime.date.today() + datetime.timedelta(days=5))
        self.assertEqual(response.context['reconciled_balance'], -175)

    def test_reconciled_balance_after_new_fiscal_year(self):
        """
        The Reconciled Balance should not be changed after creating a new
        Fiscal Year using the add_fiscal_year view.

        See Redmine Issue #194.

        """
        today = datetime.date.today()
        FiscalYear.objects.create(year=(today.year + 1), end_month=12,
                                  period=12)
        equity_header = create_header('Equity', cat_type=3)
        create_account('Retained Earnings', equity_header, 0, 3)
        create_account('Current Year Earnings', equity_header, 0, 3)
        self.test_reconcile_account_view_flip_success_pos_statement_zero_reconciled()

        response = self.client.get(
            reverse('accounts.views.reconcile_account',
                    kwargs={'account_slug': self.bank_account.slug}))

        self.assertEqual(response.context['reconciled_balance'], 275)

        response = self.client.post(reverse('fiscalyears.views.add_fiscal_year'),
                                    data={'year': today.year + 2,
                                          'end_month': 12,
                                          'period': 12,
                                          'form-TOTAL_FORMS': 0,
                                          'form-INITIAL_FORMS': 0,
                                          'form-MAX_NUM_FORMS': 0,
                                          'submit': 'Start New Year'})

        response = self.client.get(
            reverse('accounts.views.reconcile_account',
                    kwargs={'account_slug': self.bank_account.slug}))

        self.assertEqual(response.context['reconciled_balance'], 275)


class AccountDetailViewTests(TestCase):
    """
    Test Account detail view
    """
    def setUp(self):
        self.asset_header = create_header('asset', cat_type=1)
        self.liability_header = create_header('liability', cat_type=2)
        self.bank_account = create_account('bank', self.asset_header, 0, 1, True)
        self.liability_account = create_account('liability', self.liability_header, 0, 2)

    def test_show_account_detail_view_initial(self):
        """
        A `GET` to the `show_account_detail` view with an `account_slug` should
        return a DateRangeForm, start and stop_date from the 1st of Month to
        Today, an Account and all Transactions within the initial range.
        The balance counters `startbalance`, `endbalance`, `net_change`,
        `debit_total` and `credit_total` should also be returned and flipped if
        neccessary.
        """
        in_range_date = datetime.date.today()
        out_range_date = datetime.date(in_range_date.year + 20, 1, 1)
        out_range_date2 = datetime.date(in_range_date.year - 20, 1, 1)
        date_range = (datetime.date(in_range_date.year, in_range_date.month, 1), in_range_date)

        # In range entries
        general = create_entry(in_range_date, 'general entry')
        tran_general = create_transaction(general, self.bank_account, -100)

        banktran_receive = Transaction.objects.create(
            account=self.bank_account, balance_delta=-20)
        BankReceivingEntry.objects.create(
            main_transaction=banktran_receive, date=in_range_date,
            memo='receive entry', payor='test payor')
        banktran_spend = Transaction.objects.create(
            account=self.bank_account, balance_delta=50)
        BankSpendingEntry.objects.create(
            main_transaction=banktran_spend, date=in_range_date,
            memo='spend entry', ach_payment=True, payee='test payee')
        # Out of range entries
        out_general = create_entry(out_range_date, 'oor general entry')
        create_transaction(out_general, self.bank_account, -70)
        out_tran1 = Transaction.objects.create(account=self.bank_account,
                                               balance_delta=-20)
        BankReceivingEntry.objects.create(
            main_transaction=out_tran1, date=out_range_date2,
            memo='older receive entry', payor='test payor')
        out_tran2 = Transaction.objects.create(account=self.bank_account,
                                               balance_delta=50)
        BankSpendingEntry.objects.create(
            main_transaction=out_tran2, date=out_range_date,
            memo='newer spend entry', ach_payment=True, payee='test payee')

        response = self.client.get(
            reverse('accounts.views.show_account_detail',
                    kwargs={'account_slug': self.bank_account.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/account_detail.html')
        self.failUnless(isinstance(response.context['form'], DateRangeForm))
        self.assertEqual(response.context['start_date'], date_range[0])
        self.assertEqual(response.context['stop_date'], date_range[1])
        self.assertEqual(response.context['account'], self.bank_account)
        self.assertSequenceEqual(response.context['transactions'], [tran_general, banktran_receive, banktran_spend])
        self.assertEqual(response.context['debit_total'], -120)
        self.assertEqual(response.context['credit_total'], 50)
        self.assertEqual(response.context['net_change'], -70)
        # These value are flipped from expected because account.flip_balance = True
        self.assertEqual(response.context['start_balance'], 20)
        self.assertEqual(response.context['end_balance'], 90)

    def test_show_account_detail_view_initial_no_transactions(self):
        """
        A `GET` to the `show_account_detail` view with an `account_slug` for an
        Account with no Transactions should return the correct balance counters
        `startbalance`, `endbalance`, `net_change`, `debit_total` and
        `credit_total`.
        """
        response = self.client.get(
            reverse('accounts.views.show_account_detail',
                    kwargs={'account_slug': self.bank_account.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertSequenceEqual(response.context['transactions'], [])
        self.assertEqual(response.context['debit_total'], 0)
        self.assertEqual(response.context['credit_total'], 0)
        self.assertEqual(response.context['net_change'], 0)
        # These value are flipped from expected because account.flip_balance = True
        self.assertEqual(response.context['start_balance'], 0)
        self.assertEqual(response.context['end_balance'], 0)

    def test_show_account_detail_view_no_transaction_in_range(self):
        """
        A `GET` to the `show_account_detail` view with an `account_slug` for an
        Account with no Transactions in the start/stop date range should return
        the correct balance counters `startbalance`, `endbalance`,
        `net_change`, `debit_total` and `credit_total`.
        """
        out_range_date = datetime.date(datetime.date.today().year - 20, 1, 1)
        general = create_entry(out_range_date, 'general entry')
        create_transaction(general, self.bank_account, -100)
        create_transaction(general, self.liability_account, 100)
        response = self.client.get(
            reverse('accounts.views.show_account_detail',
                    kwargs={'account_slug': self.bank_account.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertSequenceEqual(response.context['transactions'], [])
        self.assertEqual(response.context['debit_total'], 0)
        self.assertEqual(response.context['credit_total'], 0)
        self.assertEqual(response.context['net_change'], 0)
        # These value are flipped from expected because account.flip_balance = True
        self.assertEqual(response.context['start_balance'], 100)
        self.assertEqual(response.context['end_balance'], 100)

    def test_show_account_detail_view_initial_only_debits(self):
        """
        A `GET` to the `show_account_detail` view with an `account_slug` for an
        Account with only debits should return the correct balance counters
        `startbalance`, `endbalance`, `net_change`, `debit_total` and
        `credit_total`.
        """

        general = create_entry(datetime.date.today(), 'general entry')
        create_transaction(general, self.liability_account, -100)

        response = self.client.get(
            reverse('accounts.views.show_account_detail',
                    kwargs={'account_slug': self.liability_account.slug}))
        self.assertEqual(response.context['debit_total'], -100)
        self.assertEqual(response.context['credit_total'], 0)
        self.assertEqual(response.context['net_change'], -100)
        # These value are flipped from expected because account.bank = True
        self.assertEqual(response.context['start_balance'], 0)
        self.assertEqual(response.context['end_balance'], -100)

    def test_show_account_detail_view_initial_only_credits(self):
        """
        A `GET` to the `show_account_detail` view with an `account_slug` for an
        Account with only credits should return the correct balance counters
        `startbalance`, `endbalance`, `net_change`, `debit_total` and
        `credit_total`.
        """

        general = create_entry(datetime.date.today(), 'general entry')
        create_transaction(general, self.liability_account, 100)

        response = self.client.get(
            reverse('accounts.views.show_account_detail',
                    kwargs={'account_slug': self.liability_account.slug}))
        self.assertEqual(response.context['debit_total'], 0)
        self.assertEqual(response.context['credit_total'], 100)
        self.assertEqual(response.context['net_change'], 100)
        # These value are flipped from expected because account.bank = True
        self.assertEqual(response.context['start_balance'], 0)
        self.assertEqual(response.context['end_balance'], 100)

    def test_show_account_detail_view_fail(self):
        """
        A `GET` to the `show_account_detail` view with an invalid `account_slug`
        should return a 404 error.
        """
        response = self.client.get(
            reverse('accounts.views.show_account_detail',
                    kwargs={'account_slug': 'does-not-exist'}))
        self.assertEqual(response.status_code, 404)

    def test_show_account_detail_view_date_success(self):
        """
        A `GET` to the `show_account_detail` view with an `account_slug`,
        start_date, and stop_date, should retrieve the Account's Transactions from
        that date period along with the respective total/change counters.
        """
        in_range_date = datetime.date.today()
        out_range_date = datetime.date(in_range_date.year + 20, 1, 1)
        out_range_date2 = datetime.date(in_range_date.year - 20, 1, 1)
        date_range = (datetime.date(in_range_date.year, 1, 1),
                      datetime.date(in_range_date.year, 12, 31))

        # In range entries
        general = create_entry(in_range_date, 'general entry')
        tran_general = create_transaction(general, self.bank_account, -100)

        banktran_receive = Transaction.objects.create(
            account=self.bank_account, balance_delta=-20)
        BankReceivingEntry.objects.create(
            main_transaction=banktran_receive, date=in_range_date,
            memo='receive entry', payor='test payor')
        banktran_spend = Transaction.objects.create(
            account=self.bank_account, balance_delta=50)
        BankSpendingEntry.objects.create(
            main_transaction=banktran_spend, date=in_range_date,
            memo='spend entry', ach_payment=True, payee='test payee')
        # Out of range entries
        out_general = create_entry(out_range_date, 'oor general entry')
        create_transaction(out_general, self.bank_account, -70)
        out_tran1 = Transaction.objects.create(account=self.bank_account,
                                               balance_delta=-20)
        BankReceivingEntry.objects.create(
            main_transaction=out_tran1, date=out_range_date2,
            memo='newer receive entry', payor='test payor')
        out_tran2 = Transaction.objects.create(account=self.bank_account,
                                               balance_delta=50)
        BankSpendingEntry.objects.create(
            main_transaction=out_tran2, date=out_range_date,
            memo='older spend entry', ach_payment=True, payee='test payee')

        response = self.client.get(
            reverse('accounts.views.show_account_detail',
                    kwargs={'account_slug': self.bank_account.slug}),
            data={'start_date': date_range[0], 'stop_date': date_range[1]})
        self.assertEqual(response.status_code, 200)
        self.failUnless(isinstance(response.context['form'], DateRangeForm))
        self.failUnless(response.context['form'].is_bound)
        self.assertEqual(response.context['start_date'], date_range[0])
        self.assertEqual(response.context['stop_date'], date_range[1])
        self.assertEqual(response.context['account'], self.bank_account)
        self.assertSequenceEqual(
            response.context['transactions'],
            [tran_general, banktran_receive, banktran_spend])
        self.assertEqual(response.context['debit_total'], -120)
        self.assertEqual(response.context['credit_total'], 50)
        self.assertEqual(response.context['net_change'], -70)
        # These value are flipped from expected because account.bank = True
        self.assertEqual(response.context['start_balance'], 20)
        self.assertEqual(response.context['end_balance'], 90)

    def test_show_account_detail_view_date_fail(self):
        """
        A `GET` to the `show_account_detail` view with an `account_slug` and
        invalid start_date or stop_date should return a DateRangeForm with errors.
        """
        response = self.client.get(
            reverse('accounts.views.show_account_detail',
                    kwargs={'account_slug': self.bank_account.slug}),
            data={'start_date': '10a/2/b98',
                  'stop_date': '11b/1threethree7/bar'})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'start_date',
                             'Enter a valid date.')
        self.assertFormError(response, 'form', 'stop_date',
                             'Enter a valid date.')

    def test_show_account_detail_view_date_in_fiscal_year(self):
        """
        A `GET` to the `show_account_detail` view with an `account_slug`,
        start_date, and stop_date will show the running balance and counters if
        the start_date is in the FiscalYear.
        """
        in_range_date = datetime.date.today()
        FiscalYear.objects.create(year=in_range_date.year, end_month=12,
                                  period=12)
        date_range = (datetime.date(in_range_date.year, 1, 1),
                      datetime.date(in_range_date.year, 12, 31))

        # In range entries
        general = create_entry(in_range_date, 'general entry')
        create_transaction(general, self.bank_account, -100)

        response = self.client.get(
            reverse('accounts.views.show_account_detail',
                    kwargs={'account_slug': self.bank_account.slug}),
            data={'start_date': date_range[0], 'stop_date': date_range[1]})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['show_balance'])

    def test_show_account_detail_view_date_no_fiscal_year(self):
        """
        A `GET` to the `show_account_detail` view with an `account_slug`,
        start_date, and stop_date will show the running balance and counters if
        there is no current FiscalYear
        """
        in_range_date = datetime.date.today()
        date_range = (datetime.date(in_range_date.year, 1, 1),
                      datetime.date(in_range_date.year, 12, 31))

        # In range entries
        general = create_entry(in_range_date, 'general entry')
        create_transaction(general, self.bank_account, -100)

        response = self.client.get(
            reverse('accounts.views.show_account_detail',
                    kwargs={'account_slug': self.bank_account.slug}),
            data={'start_date': date_range[0], 'stop_date': date_range[1]})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['show_balance'])

    def test_show_account_detail_view_date_out_fiscal_year(self):
        """
        A `GET` to the `show_account_detail` view with an `account_slug`,
        start_date, and stop_date will show the running balance and counters if
        the start_date is in the FiscalYear.
        """
        in_range_date = datetime.date.today()
        FiscalYear.objects.create(year=in_range_date.year + 2, end_month=12,
                                  period=12)
        date_range = (datetime.date(in_range_date.year, 1, 1),
                      datetime.date(in_range_date.year, 12, 31))

        # In range entries
        general = create_entry(in_range_date, 'general entry')
        create_transaction(general, self.bank_account, -100)

        response = self.client.get(
            reverse('accounts.views.show_account_detail',
                    kwargs={'account_slug': self.bank_account.slug}),
            data={'start_date': date_range[0], 'stop_date': date_range[1]})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['show_balance'])


class HistoricalAccountViewTests(TestCase):
    """
    Test the `show_account_history` view.
    """
    def test_show_account_history_view_initial_month(self):
        """
        A `GET` to the `show_account_history` view will first try to retrieve
        the Historical Accounts for the current month in the last year.
        """
        today = datetime.date.today()
        expense_historical = HistoricalAccount.objects.create(
            number='6-1001', name='Test Expense', type=6, amount='-900.25',
            date=datetime.date(
                day=1, month=today.month, year=(today.year - 1))
        )
        asset_historical = HistoricalAccount.objects.create(
            number='1-1001', name='Test Asset', type=1, amount='-9000.01',
            date=datetime.date(
                day=1, month=today.month, year=(today.year - 1))
        )

        response = self.client.get(
            reverse('accounts.views.show_account_history'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/account_history.html')
        self.assertSequenceEqual(response.context['accounts'],
                                 [asset_historical, expense_historical])

    def test_show_account_history_view_initial_recent(self):
        """
        A `GET` to the `show_account_history` view will retrieve the Historical
        Accounts for the most recent month.
        """
        today = datetime.date.today()
        # Most recent is ~2 1/4 years ago
        most_recent = datetime.date(
            day=1,
            month=today.month,
            year=today.year - 2) + datetime.timedelta(days=-93)
        expense_historical = HistoricalAccount.objects.create(
            number='6-1001', name='Test Expense', type=6, amount='-900.25',
            date=datetime.date(day=1, month=most_recent.month,
                               year=most_recent.year))
        asset_historical = HistoricalAccount.objects.create(
            number='1-1001', name='Test Asset', type=1, amount='-9000.01',
            date=datetime.date(day=1, month=most_recent.month,
                               year=most_recent.year))
        response = self.client.get(
            reverse('accounts.views.show_account_history'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/account_history.html')
        self.assertSequenceEqual(response.context['accounts'],
                                 [asset_historical, expense_historical])

    def test_show_account_history_view_initial_none(self):
        """
        A `GET` to the `show_account_history` view with No Historical Accounts
        will return an appropriate message.
        """
        response = self.client.get(reverse('accounts.views.show_account_history'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/account_history.html')
        self.assertEqual(response.context['accounts'], '')
        self.assertIn('No Account History', response.content)

    def test_show_account_history_view_by_month(self):
        """
        A `GET` to the `show_account_history` view with a `month` and `year`
        argument will retrieve the Historical Accounts for that Month and Year
        """
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
        """
        A `GET` to the `show_account_history` view with a `month` and `year`
        argument will display an error message if no Historical Accounts
        exist for the specified `month` and `year`.
        """
        today = datetime.date.today()
        response = self.client.get(reverse('accounts.views.show_account_history',
                                           kwargs={'month': today.month,
                                                   'year': today.year}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['accounts'], '')
        self.assertIn('No Account History', response.content)

    def test_show_account_history_view_by_month_fail(self):
        """
        A `GET` to the `show_account_history` view with an invalid `month`
        argument will return a 404 Error.
        """
        response = self.client.get(reverse('accounts.views.show_account_history',
                                           kwargs={'month': 90,
                                                   'year': 2012}))
        self.assertEqual(response.status_code, 404)

    def test_show_account_history_view_next(self):
        """
        A `GET` to the `show_account_history` view with `next` as a `GET`
        parameter will redirect to the next month's URL.
        """
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

        response = self.client.get(
            reverse('accounts.views.show_account_history'),
            data={'next': ''})
        self.assertRedirects(response,
                             reverse('accounts.views.show_account_history',
                                     kwargs={'month': future_month.month,
                                             'year': future_month.year}))

    def test_show_account_history_by_month_next(self):
        """
        A `GET` to the `show_account_history` view with `month` and `year`
        arguments and `next` as a `GET` parameter will redirect to the next
        month's URL
        """
        specific_date = datetime.date(day=1, month=11, year=2012)
        newer_date = datetime.date(day=1, month=12, year=2012)

        HistoricalAccount.objects.create(
            number='6-1001', name='Test Expense', type=6, amount='-900.25',
            date=newer_date)
        HistoricalAccount.objects.create(
            number='1-1001', name='Test Asset', type=1, amount='-9000.01',
            date=specific_date)
        response = self.client.get(
            reverse('accounts.views.show_account_history',
                    kwargs={'month': specific_date.month,
                            'year': specific_date.year}),
            data={'next': ''})

        self.assertRedirects(response,
                             reverse('accounts.views.show_account_history',
                                     kwargs={'month': newer_date.month,
                                             'year': newer_date.year}))

    def test_show_account_history_view_next_none(self):
        """
        A `GET` to the `show_account_history` view with `next` as a `GET`
        parameter will redirect to the same listing if there are no Historical
        Accounts for the next month.
        """
        today = datetime.date.today()
        this_month = datetime.date(year=today.year - 1, month=today.month, day=1)
        HistoricalAccount.objects.create(
            number='6-1001', name='Test Expense', type=6, amount='-900.25',
            date=this_month)
        response = self.client.get(
            reverse('accounts.views.show_account_history'), data={'next': ''})
        self.assertRedirects(response,
                             reverse('accounts.views.show_account_history',
                                     kwargs={'month': this_month.month,
                                             'year': this_month.year}))

    def test_show_account_history_view_by_month_next_none(self):
        """
        A `GET` to the `show_account_history` view with a `month` and `year`
        parameter with `next` as a `GET` parameter will redirect to the passed
        `month` and `year` if no Historical Accounts for the next `month` and
        `year` exist.
        """
        specific_date = datetime.date(day=1, month=11, year=2012)
        HistoricalAccount.objects.create(
            number='6-1001', name='Test Expense', type=6, amount='-900.25',
            date=specific_date)
        response = self.client.get(
            reverse('accounts.views.show_account_history',
                    kwargs={'month': specific_date.month,
                            'year': specific_date.year}),
            data={'next': ''})
        self.assertRedirects(response,
                             reverse('accounts.views.show_account_history',
                                     kwargs={'month': specific_date.month,
                                             'year': specific_date.year}))

    def test_show_account_history_view_previous(self):
        """
        A `GET` to the `show_account_history` view with `previous` as a `GET`
        parameter will retrieve the Historical Accounts for the last month.
        """
        today = datetime.date.today()
        last_month = today + datetime.timedelta(days=-31)
        # Accessing this month with the ?previous parameter...
        this_month = datetime.date(year=today.year - 1,
                                   month=today.month,
                                   day=1)
        # Will redirect to this month
        past_month = datetime.date(year=last_month.year - 1,
                                   month=last_month.month, day=1)

        HistoricalAccount.objects.create(
            number='6-1001', name='Test Expense', type=6, amount='-900.25',
            date=this_month)
        HistoricalAccount.objects.create(
            number='1-1001', name='Test Asset', type=1, amount='-9000.01',
            date=past_month)

        response = self.client.get(
            reverse('accounts.views.show_account_history'), data={'previous':
                                                                  ''})
        self.assertRedirects(response,
                             reverse('accounts.views.show_account_history',
                                     kwargs={'month': past_month.month,
                                             'year': past_month.year}))

    def test_show_account_history_view_by_month_previous(self):
        """
        A `GET` to the `show_account_history` view with `month` and `year`
        arguments and a `previous` `GET` parameter will redirect to the
        previous month's URL
        """
        specific_date = datetime.date(day=1, month=11, year=2012)
        older_date = datetime.date(day=1, month=10, year=2012)

        HistoricalAccount.objects.create(
            number='6-1001', name='Test Expense', type=6, amount='-900.25',
            date=older_date)
        HistoricalAccount.objects.create(
            number='1-1001', name='Test Asset', type=1, amount='-9000.01',
            date=specific_date)
        response = self.client.get(
            reverse('accounts.views.show_account_history',
                    kwargs={'month': specific_date.month,
                            'year': specific_date.year}),
            data={'previous': ''})

        self.assertRedirects(
            response,
            reverse('accounts.views.show_account_history',
                    kwargs={'month': older_date.month,
                            'year': older_date.year}))

    def test_show_account_history_view_previous_none(self):
        """
        A `GET` to the `show_account_history` view with a `month` and `year`
        parameter with `previous` as a `GET` parameter will redirect to the
        same listing if there are no Historical Accounts for the last month.
        """
        today = datetime.date.today()
        this_month = datetime.date(year=today.year - 1, month=today.month,
                                   day=1)
        HistoricalAccount.objects.create(
            number='6-1001', name='Test Expense', type=6, amount='-900.25',
            date=this_month)
        response = self.client.get(
            reverse('accounts.views.show_account_history'),
            data={'previous': ''})
        self.assertRedirects(response,
                             reverse('accounts.views.show_account_history',
                                     kwargs={'month': this_month.month,
                                             'year': this_month.year}))

    def test_show_account_history_view_by_month_previous_none(self):
        """
        A `GET` to the `show_account_history` view with `month` and `year`
        arguments and a `previous` `GET` parameter will display and error if
        no Historical Accounts for the last `month` and `year` exist.
        """
        specific_date = datetime.date(day=1, month=11, year=2012)
        HistoricalAccount.objects.create(
            number='6-1001', name='Test Expense', type=6, amount='-900.25',
            date=specific_date)
        response = self.client.get(
            reverse('accounts.views.show_account_history',
                    kwargs={'month': specific_date.month,
                            'year': specific_date.year}),
            data={'previous': ''})
        self.assertRedirects(
            response,
            reverse('accounts.views.show_account_history',
                    kwargs={'month': specific_date.month,
                            'year': specific_date.year}))


class BankJournalViewTests(TestCase):
    """
    Test view for showing Bank Entry journal for a Bank Account
    """

    def setUp(self):
        """
        Bank Entries require a Bank Account and a normal Account
        """
        self.asset_header = create_header('asset', cat_type=1)
        self.liability_header = create_header('liability', cat_type=2)
        self.bank_account = create_account('bank', self.asset_header, 0, 1, True)
        self.liability_account = create_account('liability', self.liability_header, 0, 2)

    def test_bank_journal_view_initial(self):
        """
        A `GET` to the `show_bank_journal` view should return a list of
        BankSpendingEntries and BankReceivingEntries associated with the bank
        account, from the beginning of this month to today
        """
        main_receive = Transaction.objects.create(account=self.bank_account,
                                                  balance_delta=-20,
                                                  detail='bank rec')
        receive = BankReceivingEntry.objects.create(
            main_transaction=main_receive, date=datetime.date.today(),
            memo='receive entry', payor='test payor')
        Transaction.objects.create(bankreceive_entry=receive,
                                   account=self.liability_account,
                                   balance_delta=20, detail='acc rec')

        main_spend = Transaction.objects.create(account=self.bank_account,
                                                balance_delta=50,
                                                detail='bank spend')
        spend = BankSpendingEntry.objects.create(
            main_transaction=main_spend, date=datetime.date.today(),
            memo='spend entry', ach_payment=True, payee='test payee')
        Transaction.objects.create(bankspend_entry=spend,
                                   account=self.liability_account,
                                   balance_delta=-50, detail='acc spend')

        response = self.client.get(
            reverse('accounts.views.bank_journal',
                    kwargs={'account_slug': self.bank_account.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/bank_journal.html')
        self.failUnless(isinstance(response.context['form'], DateRangeForm))
        self.assertItemsEqual(
            response.context['transactions'],
            Transaction.objects.filter(account=self.bank_account))
        today = datetime.date.today()
        self.assertEqual(response.context['start_date'],
                         datetime.date(today.year, today.month, 1))
        self.assertEqual(response.context['stop_date'], today)

    def test_bank_journal_view_date_filter(self):
        """
        A `GET` to the `show_bank_journal` view submitted with a `start_date`
        and `stop_date` returns the Bank Entries for the account during the time
        period
        """
        date_range = ('1/1/11', '3/7/12')
        in_range_date = datetime.date(2012, 1, 1)
        out_range_date = datetime.date(2013, 5, 8)
        out_range_date2 = datetime.date(2010, 12, 1)

        banktran_receive = Transaction.objects.create(
            account=self.bank_account, balance_delta=-20)
        receive = BankReceivingEntry.objects.create(
            main_transaction=banktran_receive, date=in_range_date,
            memo='receive entry', payor='test payor')
        Transaction.objects.create(bankreceive_entry=receive,
                                   account=self.liability_account,
                                   balance_delta=20)

        banktran_spend = Transaction.objects.create(account=self.bank_account,
                                                    balance_delta=50)
        spend = BankSpendingEntry.objects.create(
            main_transaction=banktran_spend, date=in_range_date,
            memo='spend entry', ach_payment=True, payee='test payee')
        Transaction.objects.create(bankspend_entry=spend,
                                   account=self.liability_account,
                                   balance_delta=-50)

        out_tran1 = Transaction.objects.create(account=self.bank_account,
                                               balance_delta=-20)
        out_receive = BankReceivingEntry.objects.create(
            main_transaction=out_tran1, date=out_range_date2,
            memo='newer receive entry', payor='test payor')
        Transaction.objects.create(bankreceive_entry=out_receive,
                                   account=self.liability_account,
                                   balance_delta=20)

        out_tran2 = Transaction.objects.create(account=self.bank_account,
                                               balance_delta=50)
        out_spend = BankSpendingEntry.objects.create(
            main_transaction=out_tran2, date=out_range_date,
            memo='older spend entry', ach_payment=True, payee='test payee')
        Transaction.objects.create(bankspend_entry=out_spend,
                                   account=self.liability_account,
                                   balance_delta=-50)

        response = self.client.get(
            reverse('accounts.views.bank_journal',
                    args=[self.bank_account.slug]),
            data={'start_date': date_range[0], 'stop_date': date_range[1]})

        self.assertEqual(response.status_code, 200)
        self.assertItemsEqual(response.context['transactions'],
                              [banktran_receive, banktran_spend])
        self.assertEqual(response.context['start_date'],
                         datetime.date(2011, 1, 1))
        self.assertEqual(response.context['stop_date'],
                         datetime.date(2012, 3, 7))
