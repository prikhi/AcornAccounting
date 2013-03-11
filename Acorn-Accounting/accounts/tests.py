"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
import datetime

from django.template.defaultfilters import slugify
from django.test import TestCase

from models import Header, Account, JournalEntry, Transaction


def create_header(name, parent=None, cat_type=2):
    return Header.objects.create(name=name, parent=parent, type=cat_type, slug=slugify(name))


def create_account(name, parent, balance, cat_type=2):
    return Account.objects.create(name=name, slug=slugify(name), parent=parent, balance=balance,
                                  type=cat_type)


def create_entry(date, memo):
    return JournalEntry.objects.create(date=date, memo=memo)


def create_transaction(entry, account, delta):
    return Transaction.objects.create(journal_entry=entry, account=account,
                                      balance_delta=delta)


class BaseAccountModelTest(TestCase):
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

        entry = create_entry(datetime.datetime.today(), 'Entry')
        create_transaction(entry, asset_acc, -20)
        create_transaction(entry, expense_acc, -20)
        create_transaction(entry, cost_acc, -20)
        create_transaction(entry, oth_expense_acc, -20)
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
        self.assertEqual(asset_acc.get_balance(), -20)
        self.assertEqual(asset_header.get_account_balance(), -20)
        self.assertEqual(expense_acc.get_balance(), -20)
        self.assertEqual(expense_header.get_account_balance(), -20)
        self.assertEqual(cost_acc.get_balance(), -20)
        self.assertEqual(cost_header.get_account_balance(), -20)
        self.assertEqual(oth_expense_acc.get_balance(), -20)
        self.assertEqual(oth_expense_header.get_account_balance(), -20)


class TransactionTest(TestCase):
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
        self.assertEqual(debited.balance, -20)
        self.assertEqual(credited.balance, 20)

    def test_account_change(self):
        '''
        Tests that balance_delta is refunded when Account changes
        '''
        header = create_header('Account Change')
        source = create_account('Source', header, 0)
        target = create_account('Target', header, 0)
        entry = create_entry(datetime.date.today(), 'Entry')
        trans = create_transaction(entry=entry, account=source, delta=-20)
        trans.account = target
        trans.save()
        source = Account.objects.get(id=source.id)
        target = Account.objects.get(id=target.id)
        self.assertEqual(target.balance, -20)
        self.assertEqual(source.balance, 0)

    def test_balance_change(self):
        '''
        Tests that balance change first refunds instead of being cumulative
        '''
        header = create_header('Account Change')
        source = create_account('Source', header, 0)
        entry = create_entry(datetime.date.today(), 'Entry')
        trans = create_transaction(entry=entry, account=source, delta=-20)
        source = Account.objects.get(id=source.id)
        trans.balance_delta = 0
        trans.save()
        source = Account.objects.get(id=source.id)
        self.assertEqual(source.balance, 0)

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
        source = Account.objects.get(id=source.id)
        trans.account = target
        trans.balance_delta = 20
        trans.save()
        source = Account.objects.get(id=source.id)
        target = Account.objects.get(id=target.id)
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
        self.assertEqual(source.get_balance(), 0)

    def test_one_transaction_account_balance(self):
        '''
        Tests get_final_account_balance for a single transaction
        '''
        header = create_header('Initial')
        source = create_account('Source', header, 0)
        entry = create_entry(datetime.date.today(), 'Entry')
        trans = create_transaction(entry=entry, account=source, delta=-20)
        self.assertEqual(trans.get_final_account_balance(), -20)

    def test_two_transactions_account_balance(self):
        '''
        Tests get_final_account_balance for transactions in the same entry
        '''
        header = create_header('Initial')
        source = create_account('Source', header, 0)
        entry = create_entry(datetime.date.today(), 'Entry')
        trans_low_id = create_transaction(entry=entry, account=source, delta=-20)
        trans_high_id = create_transaction(entry=entry, account=source, delta=-20)
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
        trans_low_id = create_transaction(entry=entry, account=source, delta=-20)
        trans_high_id = create_transaction(entry=entry2, account=source, delta=-20)
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
        trans_newer = create_transaction(entry=entry, account=source, delta=-20)
        trans_older = create_transaction(entry=entry2, account=source, delta=-20)
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
        trans_older = create_transaction(entry=entry2, account=source, delta=-20)
        trans_newer = create_transaction(entry=entry, account=source, delta=-20)
        self.assertEqual(trans_older.get_final_account_balance(), -20)
        self.assertEqual(trans_newer.get_final_account_balance(), -40)
