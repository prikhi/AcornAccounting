import datetime

from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.utils.timezone import utc

from core.tests import (create_header, create_entry, create_account,
                        create_transaction)

from accounts.models import Account
from core.forms import DateRangeForm
from events.models import Event
from fiscalyears.models import FiscalYear

from .forms import (JournalEntryForm, TransactionFormSet, TransferFormSet,
                    BankReceivingForm, BankReceivingTransactionFormSet,
                    BankSpendingForm, BankSpendingTransactionFormSet)
from .models import (Transaction, JournalEntry, BankSpendingEntry,
                     BankReceivingEntry)


class JournalEntryModelTests(TestCase):
    """Tests custom methods on the BaseJournalEntry model."""
    def test_in_fiscal_year_no_fiscal_year(self):
        """
        If there is no current Fiscal Year, the `in_fiscal_year` method will
        return `True`.
        """
        entry = JournalEntry.objects.create(date=datetime.date.today(),
                                            memo='no fiscal year')
        self.assertTrue(entry.in_fiscal_year())

    def test_in_fiscal_year_before_start(self):
        """
        If there is a Fiscal Year, the `in_fiscal_year` method will return
        `False` if the Entry's date is before the FiscalYear's start.
        """
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        entry_date = datetime.date(2011, 2, 5)
        entry = JournalEntry.objects.create(
            date=entry_date, memo='before fiscal year')
        self.assertEqual(FiscalYear.objects.current_start(),
                         datetime.date(2012, 1, 1))
        self.assertFalse(entry.in_fiscal_year())

    def test_in_fiscal_year_after_start(self):
        """
        If there is a Fiscal Year, the `in_fiscal_year` method will return
        `False` if the Entry's date is before the FiscalYear's start.
        """
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
        """
        Tests that BankSpendingEntry Models requires either an ACH payment or
        check_number
        refs #97
        """
        main_transaction = Transaction.objects.create(account=self.account,
                                                      balance_delta=25)
        entry = BankSpendingEntry(
            check_number=None, ach_payment=None, memo='no check or ach',
            main_transaction=main_transaction, date=datetime.date.today())
        self.assertRaises(ValidationError, entry.save)

    def test_ach_xor_check_number(self):
        """
        Tests that BankSpendingEntry Models requires either an ACH payment OR
        check_number exclusively
        refs #97
        """
        main_transaction = Transaction.objects.create(account=self.account,
                                                      balance_delta=25)
        entry = BankSpendingEntry(
            check_number="23", ach_payment=True, memo='check AND ach',
            main_transaction=main_transaction, date=datetime.date.today())
        self.assertRaises(ValidationError, entry.save)

    def test_save_set_transaction_date(self):
        """
        Saving a BankSpendingEntry should set the ``date`` fields of it's
        ``main_transaction`` and the ``Transactions`` in it's
        ``transaction_set``.
        """
        date = datetime.date.today() - datetime.timedelta(days=42)
        main_transaction = Transaction.objects.create(account=self.account,
                                                      balance_delta=25)
        entry = BankSpendingEntry.objects.create(
            check_number="23", memo='change date',
            main_transaction=main_transaction, date=datetime.date.today())
        tran = Transaction.objects.create(bankspend_entry=entry,
                                          account=self.account,
                                          balance_delta=15)

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

    def test_save_new_void_entry(self):
        """A void Entry should be able to be created."""
        main_transaction = Transaction.objects.create(account=self.account,
                                                      balance_delta=0)
        entry = BankSpendingEntry.objects.create(
            check_number="23", memo='Entry', main_transaction=main_transaction,
            date=datetime.date.today())
        entry.void = True
        entry.save()

        self.assertEqual(BankSpendingEntry.objects.count(), 1)

    def test_save_make_void_with_transactions(self):
        """
        Making an Entry void should delete it's Transactions, zero it's
        main_transaction and append VOID to the memo.
        """
        main_transaction = Transaction.objects.create(account=self.account,
                                                      balance_delta=25)
        entry = BankSpendingEntry.objects.create(
            check_number="23", memo='Entry', main_transaction=main_transaction,
            date=datetime.date.today())
        Transaction.objects.create(bankspend_entry=entry, account=self.account,
                                   balance_delta=15)

        entry.void = True
        entry.save()

        self.assertEqual(Transaction.objects.count(), 1)
        main_transaction = Transaction.objects.get()
        self.assertEqual(main_transaction.balance_delta, 0)
        entry = BankSpendingEntry.objects.get()
        self.assertIn("VOID", entry.memo)
        self.assertEqual(entry.transaction_set.count(), 0)

    def test_save_unvoid_and_add_transactions(self):
        """
        Void Entries must be unvoided to add transactions.
        """
        self.test_save_make_void_with_transactions()

        entry = BankSpendingEntry.objects.get()
        entry.void = False
        entry.save()

        Transaction.objects.create(bankspend_entry=entry, account=self.account,
                                   balance_delta=15)

        self.assertEqual(Transaction.objects.count(), 2)

    def test_unique_check_number_per_account(self):
        """
        A BankSpendingEntry's `check_number` should not be unique globally, but
        per Account by the `main_transaction` attribute.
        """
        second_account = create_account('Account 2', self.header, 0)
        main_transaction1 = Transaction.objects.create(account=self.account,
                                                       balance_delta=25)
        BankSpendingEntry.objects.create(check_number=1, ach_payment=False,
                                         memo='check 1 account 1',
                                         main_transaction=main_transaction1,
                                         date=datetime.date.today())
        main_transaction2 = Transaction.objects.create(account=second_account,
                                                       balance_delta=25)
        BankSpendingEntry.objects.create(check_number=1, ach_payment=False,
                                         memo='check 1 account 2',
                                         main_transaction=main_transaction2,
                                         date=datetime.date.today())

        self.assertEqual(BankSpendingEntry.objects.count(), 2)

    def test_unique_check_number_per_account_fail(self):
        """
        A BankSpendingEntry's `check_number` should not be unique globally, but
        per Account by the `main_transaction` attribute.
        A BankSpendingEntry with the same `check_number` as another
        BankSpendingEntry whose main_transactions have the same Account, is
        invalid.
        """
        main_transaction1 = Transaction.objects.create(account=self.account,
                                                       balance_delta=25)
        BankSpendingEntry.objects.create(check_number=1, ach_payment=False,
                                         memo='check 1 account 1',
                                         main_transaction=main_transaction1,
                                         date=datetime.date.today())
        main_transaction2 = Transaction.objects.create(account=self.account,
                                                       balance_delta=25)
        second_entry = BankSpendingEntry(check_number=1, ach_payment=False,
                                         memo='check 1 account 2',
                                         main_transaction=main_transaction2,
                                         date=datetime.date.today())

        self.assertRaises(ValidationError, second_entry.save)


class BankReceivingEntryModelTests(TestCase):
    """Test the custom BankSpendingEntry model methods"""
    def setUp(self):
        self.header = create_header('Initial')
        self.account = create_account('Account', self.header, 0)

    def test_save_set_transaction_date(self):
        """
        Saving a BankReceivingEntry should set the ``date`` fields of it's
        ``main_transaction`` and the ``Transactions`` in it's
        ``transaction_set``.
        """
        date = datetime.date.today() - datetime.timedelta(days=42)
        main_transaction = Transaction.objects.create(account=self.account,
                                                      balance_delta=25)
        entry = BankReceivingEntry.objects.create(
            payor='test payor', memo='change date',
            main_transaction=main_transaction, date=datetime.date.today())
        tran = Transaction.objects.create(
            bankreceive_entry=entry, account=self.account, balance_delta=15)
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
        """
        Tests that created Transactions affect Account balances.
        """
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
        """
        Tests that balance_delta is refunded when Account changes.
        """
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
        """
        Tests that balance change first refunds instead of being cumulative
        """
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
        """
        Tests that balance_delta is refunded to source account and new
        balance_delta is applied to target account
        """
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
        """
        Test that Transactions refund Accounts on deletion
        """
        header = create_header('Initial')
        source = create_account('Source', header, 0)
        entry = create_entry(datetime.date.today(), 'Entry')
        trans = create_transaction(entry=entry, account=source, delta=-20)
        trans.delete()
        source = Account.objects.all()[0]
        self.assertEqual(source.get_balance(), 0)

    def test_one_transaction_account_balance(self):
        """
        Tests get_final_account_balance for a single transaction
        """
        header = create_header('Initial')
        source = create_account('Source', header, 0)
        entry = create_entry(datetime.date.today(), 'Entry')
        create_transaction(entry=entry, account=source, delta=-20)
        trans = Transaction.objects.all()[0]
        self.assertEqual(trans.get_final_account_balance(), -20)

    def test_two_transactions_account_balance(self):
        """
        Tests get_final_account_balance for transactions in the same entry
        """
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
        """
        Tests get_final_account_balance for transactions with different entries
        but same dates
        """
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
        """
        Tests get_final_account_balance for older transactions with higher ids
        """
        header = create_header('Initial')
        source = create_account('Source', header, 0)
        entry = create_entry(datetime.date.today(), 'Entry')
        entry2 = create_entry(datetime.date.today() -
                              datetime.timedelta(days=2), 'Entry2')
        create_transaction(entry=entry, account=source, delta=-20)
        create_transaction(entry=entry2, account=source, delta=-20)
        trans_newer = Transaction.objects.all()[1]
        trans_older = Transaction.objects.all()[0]
        self.assertEqual(trans_older.get_final_account_balance(), -20)
        self.assertEqual(trans_newer.get_final_account_balance(), -40)

    def test_two_transactions_old_first_account_balance(self):
        """
        Tests get_final_account_balance for older transactions with lower ids
        """
        header = create_header('Initial')
        source = create_account('Source', header, 0)
        entry = create_entry(datetime.date.today(), 'Entry')
        entry2 = create_entry(datetime.date.today() -
                              datetime.timedelta(days=2), 'Entry2')
        create_transaction(entry=entry2, account=source, delta=-20)
        create_transaction(entry=entry, account=source, delta=-20)
        trans_older = Transaction.objects.all()[0]
        trans_newer = Transaction.objects.all()[1]
        self.assertEqual(trans_older.get_final_account_balance(), -20)
        self.assertEqual(trans_newer.get_final_account_balance(), -40)

    def test_transaction_get_journal_entry(self):
        """
        Tests that get_journal_entry retrieves the correct JournalEntry
        """
        header = create_header('Initial')
        bank_account = create_account('Bank Account', header, 0, cat_type=1,
                                      bank=True)
        account = create_account('Account', header, 0)

        journal_entry = create_entry(datetime.date.today(), 'test entry')
        je_tran = create_transaction(journal_entry, account, 25)
        self.assertEqual(je_tran.get_journal_entry(), journal_entry)

        bankspend_main = Transaction.objects.create(account=bank_account,
                                                    balance_delta=50)
        bankspend = BankSpendingEntry.objects.create(
            date=datetime.date.today(), memo='test bankspend',
            main_transaction=bankspend_main, ach_payment=True)
        bankspend_tran = Transaction.objects.create(bankspend_entry=bankspend,
                                                    account=account,
                                                    balance_delta=-50)
        self.assertEqual(bankspend_main.get_journal_entry(), bankspend)
        self.assertEqual(bankspend_tran.get_journal_entry(), bankspend)

        bankreceive_main = Transaction.objects.create(account=bank_account,
                                                      balance_delta=-50)
        bankreceive = BankSpendingEntry.objects.create(
            date=datetime.date.today(), memo='test bank receive',
            main_transaction=bankreceive_main, ach_payment=True)
        bankreceive_tran = Transaction.objects.create(
            bankspend_entry=bankreceive, account=account, balance_delta=50)
        self.assertEqual(bankreceive_main.get_journal_entry(), bankreceive)
        self.assertEqual(bankreceive_tran.get_journal_entry(), bankreceive)

    def test_transaction_save_date(self):
        """
        Saving a Transaction should cause the Transaction to use the ``date``
        value of it's ``journal_entry``.
        """
        date = datetime.date.today() - datetime.timedelta(days=42)
        header = create_header('Account Change')
        source = create_account('Source', header, 0)
        entry = create_entry(date, 'test entry')
        trans = create_transaction(entry, source, 20)
        self.assertEqual(trans.date, date)

    def test_transaction_save_date_no_pull(self):
        """
        Saving a Transaction with a ``pull_date`` of ``False`` will cause the
        Transaction to not use it's ``journal_entry`` ``date`` to populate it's
        ``date`` field.
        """
        date = datetime.date.today() - datetime.timedelta(days=42)
        header = create_header('Account Change')
        source = create_account('Source', header, 0)
        entry = create_entry(date, 'test entry')
        trans = Transaction(journal_entry=entry, account=source,
                            balance_delta=20)
        trans.save(pull_date=False)
        self.assertEqual(trans.date, None)
        trans.date = datetime.date.today()
        trans.save(pull_date=False)
        self.assertEqual(trans.date, datetime.date.today())
        trans.save(pull_date=True)
        self.assertEqual(trans.date, date)

    def test_transaction_clean_void_fail(self):
        """It is not possible to belong to a void BankSpendingEntry."""
        header = create_header('Header')
        account = create_account('Account', header, 0)
        main_transaction = Transaction.objects.create(account=account,
                                                      balance_delta=25)
        entry = BankSpendingEntry.objects.create(
            check_number="23", memo='Entry', main_transaction=main_transaction,
            date=datetime.date.today())
        entry.void = True
        entry.save()
        entry = BankSpendingEntry.objects.get()

        trans = Transaction(bankspend_entry=entry, account=account,
                            balance_delta=15)

        self.assertRaises(ValidationError, trans.save)


class JournalEntryViewTests(TestCase):
    """
    Test JournalEntry add and detail views
    """
    def setUp(self):
        """
        JournalEntries require two accounts
        """
        self.asset_header = create_header('asset', cat_type=1)
        self.expense_header = create_header('expense', cat_type=6)
        self.asset_account = create_account('asset', self.asset_header, 0, 1)
        self.expense_account = create_account('expense', self.expense_header,
                                              0, 6)
        self.event = Event.objects.create(name='test event 1',
                                          date=datetime.date.today(),
                                          number='1', city='min', state='VA')

    def test_journal_add_view_initial(self):
        """
        A `GET` to the `add_journal_entry` view should display JournalEntry
        Form and Transaction Formset.
        """
        response = self.client.get(reverse('entries.views.add_journal_entry'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'entries/entry_add.html')
        self.failUnless(isinstance(response.context['entry_form'],
                                   JournalEntryForm))
        self.assertEqual(response.context['journal_type'], 'GJ')
        self.failUnless(isinstance(response.context['transaction_formset'],
                                   TransactionFormSet))

    def test_add_journal_entry_view_success(self):
        """
        A `POST` to the `add_journal_entry` view with valid data will create a
        JournalEntry and it's respective Transactions.
        """
        response = self.client.post(
            reverse('entries.views.add_journal_entry'),
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
        entry = JournalEntry.objects.get(memo='test GJ entry')
        self.assertRedirects(response,
                             reverse('entries.views.show_journal_entry',
                                     kwargs={'entry_id': entry.id}))
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertEqual(Account.objects.all()[0].balance, -5)
        self.assertEqual(Account.objects.all()[1].balance, 5)

    def test_add_journal_entry_view_fail_entry(self):
        """
        A `POST` to the `add_journal_entry` view with invalid entry data will
        not create a JournalEntry or Transactions and displays an error
        message.
        """
        response = self.client.post(
            reverse('entries.views.add_journal_entry'),
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
        self.assertFormError(response, 'entry_form', 'date',
                             'This field is required.')
        self.assertFormError(response, 'entry_form', 'memo',
                             'This field is required.')
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(Account.objects.get(name='asset').balance, 0)
        self.assertEqual(Account.objects.get(name='expense').balance, 0)

    def test_add_journal_entry_view_fail_out_of_balance(self):
        """
        A `POST` to the `add_journal_entry` view with invalid Transaction data
        should not create a JournalEntry or Transactions and displays an error
        message.
        """
        response = self.client.post(
            reverse('entries.views.add_journal_entry'),
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
        self.assertEqual(
            response.context['transaction_formset'].non_form_errors()[0],
            "The total amount of Credits must be equal to the total amount of "
            "Debits.")
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(Account.objects.get(name='asset').balance, 0)
        self.assertEqual(Account.objects.get(name='expense').balance, 0)

    def test_add_journal_entry_view_transactions_required_valid(self):
        """
        A `POST` to the `add_journal_entry` view should have at least one
        Transaction. If not an Error should appear even if the deleted form is
        valid.

        See Redmine Issue #153.
        """
        response = self.client.post(
            reverse('entries.views.add_journal_entry'),
            data={'entry-date': '4/20/2013',
                  'entry-memo': 'test bug regression',
                  'transaction-TOTAL_FORMS': 20,
                  'transaction-INITIAL_FORMS': 0,
                  'transaction-MAX_NUM_FORMS': '',
                  'transaction-0-id': '',
                  'transaction-0-account': self.asset_account.id,
                  'trnasaction-0-credit': 12,
                  'transaction-0-DELETE': 'on',
                  'transaction-1-id': '',
                  'transaction-1-account': self.asset_account.id,
                  'trnasaction-1-debit': 12,
                  'subbtn': 'Submit',
                  })

        self.assertEqual(response.status_code, 200)
        self.failIf(response.context['transaction_formset'].is_valid())
        self.assertEqual(
            response.context['transaction_formset'].non_form_errors()[0],
            "At least one Transaction is required to create an Entry.")
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(Account.objects.get(name='asset').balance, 0)
        self.assertEqual(Account.objects.get(name='expense').balance, 0)

    def test_add_journal_entry_view_transactions_required_invalid(self):
        """
        A `POST` to the `add_journal_entry` view should have at least one
        Transaction. If not an Error should appear even if the deleted form is
        invalid.

        See Redmine Issue #153.
        """
        response = self.client.post(
            reverse('entries.views.add_journal_entry'),
            data={'entry-date': '4/20/2013',
                  'entry-memo': 'test bug regression',
                  'transaction-TOTAL_FORMS': 20,
                  'transaction-INITIAL_FORMS': 0,
                  'transaction-MAX_NUM_FORMS': '',
                  'transaction-0-account': self.asset_account.id,
                  'transaction-0-DELETE': 'on',
                  'subbtn': 'Submit',
                  })

        self.assertEqual(response.status_code, 200)
        self.failIf(response.context['transaction_formset'].is_valid())
        self.assertEqual(
            response.context['transaction_formset'].non_form_errors()[0],
            "At least one Transaction is required to create an Entry.")
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(Account.objects.get(name='asset').balance, 0)
        self.assertEqual(Account.objects.get(name='expense').balance, 0)

    def test_add_journal_entry_view_fail_deleted_and_out_of_balance(self):
        """
        A `POST` to the `add_journal_entry` view with a deleted form and out of
        balance total should not create a JournalEntry or Transactions and
        displays an error message.

        See Redmine Issue #123.
        """
        response = self.client.post(
            reverse('entries.views.add_journal_entry'),
            data={'entry-date': '4/20/2013',
                  'entry-memo': 'test bug regression',
                  'transaction-TOTAL_FORMS': 20,
                  'transaction-INITIAL_FORMS': 0,
                  'transaction-MAX_NUM_FORMS': '',
                  'transaction-0-id': '',
                  'transaction-0-journal_entry': '',
                  'transaction-0-detail': 'test detail',
                  'transaction-0-credit': '',
                  'transaction-0-account': self.asset_account.id,
                  'transaction-0-DELETE': 'on',
                  'transaction-1-id': '',
                  'transaction-1-journal_entry': '',
                  'transaction-1-detail': '',
                  'transaction-1-debit': 2,
                  'transaction-1-account': self.expense_account.id,
                  'subbtn': 'Submit',
                  })
        self.assertEqual(response.status_code, 200)
        self.failIf(response.context['transaction_formset'].is_valid())
        self.assertEqual(
            response.context['transaction_formset'].non_form_errors(),
            ["The total amount of Credits must be equal to the total amount "
             "of Debits."])
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(Account.objects.get(name='asset').balance, 0)
        self.assertEqual(Account.objects.get(name='expense').balance, 0)

    def test_add_journal_entry_view_fail_transactions_empty(self):
        """
        A `POST` to the `add_journal_entry` view with no Transaction data
        should not create a JournalEntry or Transactions and displays an error
        message.
        refs #88: Empty Entries are Allowed to be Submit
        """
        response = self.client.post(
            reverse('entries.views.add_journal_entry'),
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
        self.assertEqual(
            response.context['transaction_formset'].forms[0].errors['account'],
            ['This field is required.'])
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(Account.objects.get(name='asset').balance, 0)
        self.assertEqual(Account.objects.get(name='expense').balance, 0)

    def test_add_journal_entry_view_add_another(self):
        """
        A `POST` to the `add_journal_entry` view with valid data and a submit
        value of 'Submit & Add More' will create a JournalEntry and it's
        respective Transactions, redirecting back to the Add page.
        """
        response = self.client.post(
            reverse('entries.views.add_journal_entry'),
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
        self.assertRedirects(response,
                             reverse('entries.views.add_journal_entry'))
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertEqual(Account.objects.all()[0].balance, -5)
        self.assertEqual(Account.objects.all()[1].balance, 5)

    def test_add_journal_entry_view_delete(self):
        """
        A `POST` to the `add_journal_entry` view with a `entry_id` and a submit
        value of 'Delete' will delete the JournalEntry and all related
        Transactions, refunding the respective Accounts.
        """
        entry = create_entry(datetime.date.today(), 'test memo')
        create_transaction(entry, self.asset_account, 50)
        create_transaction(entry, self.expense_account, -50)

        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertEqual(Account.objects.get(name='asset').balance, 50)
        self.assertEqual(Account.objects.get(name='expense').balance, -50)

        response = self.client.post(reverse('entries.views.add_journal_entry',
                                            kwargs={'entry_id': entry.id}),
                                    data={'delete': 'Delete'})

        self.assertRedirects(response,
                             reverse('entries.views.journal_ledger'))
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(Account.objects.get(name='asset').balance, 0)
        self.assertEqual(Account.objects.get(name='expense').balance, 0)

    def test_add_journal_entry_view_delete_fail(self):
        """
        A `POST` to the `add_journal_entry` view with an invalid `entry_id`
        will return a 404.
        """
        self.assertEqual(JournalEntry.objects.count(), 0)
        response = self.client.post(reverse('entries.views.add_journal_entry',
                                            kwargs={'entry_id': 9001}),
                                    data={'delete': 'Delete'})
        self.assertEqual(response.status_code, 404)

    def test_add_journal_entry_view_fiscal_year(self):
        """
        A `POST` to the ``add_journal_entry`` view with a ``date`` on or after
        the start of the current ``FiscalYear`` will create a JournalEntry and
        Transactions.  If there is only one FiscalYear, the ``period`` amount
        of months before the ``end_month`` is used.
        """
        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        response = self.client.post(
            reverse('entries.views.add_journal_entry'),
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
        entry = JournalEntry.objects.get(memo='test GJ entry')
        self.assertRedirects(response,
                             reverse('entries.views.show_journal_entry',
                                     kwargs={'entry_id': entry.id}))
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertEqual(Account.objects.all()[0].balance, -5)
        self.assertEqual(Account.objects.all()[1].balance, 5)

    def test_add_journal_entry_view_fail_fiscal_year(self):
        """
        A `POST` to the ``add_journal_entry`` view with a ``date`` before
        the start of the current ``FiscalYear`` will not create a JournalEntry
        or Transactions and displays and error message.
        If there is only one FiscalYear, the ``period`` amount of months before
        the ``end_month`` is used.
        """
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        response = self.client.post(
            reverse('entries.views.add_journal_entry'),
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
        self.assertFormError(
            response, 'entry_form', 'date', 'The date must be in the current '
            'Fiscal Year.')
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(Account.objects.get(name='asset').balance, 0)
        self.assertEqual(Account.objects.get(name='expense').balance, 0)

    def test_add_journal_entry_view_two_fiscal_year(self):
        """
        A `POST` to the ``add_journal_entry`` view with a ``date`` on or after
        the start of the current ``FiscalYear`` will create a JournalEntry
        and Transactions.
        If there is are multiple FiscalYear, the ``date`` cannot be before the
        ``end_month`` of the Second to Latest FiscalYear.
        """
        FiscalYear.objects.create(year=2010, end_month=12, period=12)
        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        response = self.client.post(
            reverse('entries.views.add_journal_entry'),
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
        entry = JournalEntry.objects.get(memo='test GJ entry')
        self.assertRedirects(response,
                             reverse('entries.views.show_journal_entry',
                                     kwargs={'entry_id': entry.id}))
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertEqual(Account.objects.all()[0].balance, -5)
        self.assertEqual(Account.objects.all()[1].balance, 5)

    def test_add_journal_entry_view_fail_two_fiscal_year(self):
        """
        A `POST` to the ``add_journal_entry`` view with a ``date`` before
        the start of the current ``FiscalYear`` will not create a JournalEntry
        or Transactions and displays and error message.
        If there is are multiple FiscalYear, the ``date`` cannot be before the
        ``end_month`` of the Second to Latest FiscalYear.
        """
        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        response = self.client.post(
            reverse('entries.views.add_journal_entry'),
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
        self.assertFormError(
            response, 'entry_form', 'date', 'The date must be in the current '
            'Fiscal Year.')
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(Account.objects.get(name='asset').balance, 0)
        self.assertEqual(Account.objects.get(name='expense').balance, 0)

    def test_add_journal_entry_view_edit_no_fiscal_year(self):
        """
        A `GET` to the `add_journal_entry` view with a `entry_id` will return a
        JournalEntryForm and TransactionFormSet with the specified JournalEntry
        instance if there is no current FiscalYear.
        """
        self.test_add_journal_entry_view_success()
        entry = JournalEntry.objects.all()[0]
        response = self.client.get(
            reverse('entries.views.add_journal_entry',
                    kwargs={'entry_id': JournalEntry.objects.all()[0].id}))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'entries/entry_add.html')
        self.failUnless(isinstance(response.context['entry_form'],
                                   JournalEntryForm))
        self.failUnless(isinstance(response.context['transaction_formset'],
                                   TransactionFormSet))
        self.assertEqual(response.context['entry_form'].instance, entry)
        self.assertEqual(
            response.context['transaction_formset'].forms[0].instance,
            entry.transaction_set.all()[0])
        self.assertEqual(
            response.context['transaction_formset'].forms[1].instance,
            entry.transaction_set.all()[1])
        self.assertEqual(
            response.context['transaction_formset'].forms[0].initial['debit'],
            5)
        self.assertEqual(
            response.context['transaction_formset'].forms[1].initial['credit'],
            5)

    def test_add_journal_entry_view_edit_in_fiscal_year(self):
        """
        A `GET` to the `add_journal_entry` view with a `entry_id` will return a
        JournalEntryForm and TransactionFormSet with the specified JournalEntry
        instance if the entry is in the current Fiscal Year
        """
        today = datetime.date.today()
        FiscalYear.objects.create(year=today.year, end_month=12, period=12)
        self.test_add_journal_entry_view_success()
        entry = JournalEntry.objects.all()[0]
        response = self.client.get(reverse('entries.views.add_journal_entry',
                                           kwargs={'entry_id': entry.id}))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'entries/entry_add.html')

    def test_add_journal_entry_view_edit_out_of_fiscal_year(self):
        """
        A `GET` to the `add_journal_entry` view with a `entry_id` will return
        a 404 Error if the entry is before the current Fiscal Year.
        """
        self.test_add_journal_entry_view_success()
        today = datetime.date.today()
        FiscalYear.objects.create(year=today.year + 2, end_month=12, period=12)
        entry = JournalEntry.objects.all()[0]
        response = self.client.get(reverse('entries.views.add_journal_entry',
                                           kwargs={'entry_id': entry.id}))

        self.assertEqual(response.status_code, 404)

    def test_add_journal_entry_view_edit_account_success(self):
        """
        A `POST` to the `add_journal_entry` view with a `entry_id` should
        modify the JournalEntry and it's Transactions with the POSTed data and
        redirect to the Entry's detail page.
        """
        self.test_add_journal_entry_view_success()
        entry = JournalEntry.objects.all()[0]
        response = self.client.post(
            reverse('entries.views.add_journal_entry',
                    kwargs={'entry_id': JournalEntry.objects.all()[0].id}),
            data={'entry-date': '5/1/11',
                  'entry-memo': 'new memo!',
                  'transaction-TOTAL_FORMS': 22,
                  'transaction-INITIAL_FORMS': 2,
                  'transaction-MAX_NUM_FORMS': '',
                  'transaction-0-id': Transaction.objects.all()[0].id,
                  'transaction-0-journal_entry': entry.id,
                  'transaction-0-account': self.expense_account.id,
                  'transaction-0-debit': 5,
                  'transaction-0-detail': 'debit',
                  'transaction-0-event': self.event.id,
                  'transaction-1-id': Transaction.objects.all()[1].id,
                  'transaction-1-journal_entry': entry.id,
                  'transaction-1-account': self.asset_account.id,
                  'transaction-1-credit': 5,
                  'transaction-1-detail': 'credit',
                  'subbtn': 'Submit'})
        self.assertRedirects(
            response,
            reverse('entries.views.show_journal_entry',
                    kwargs={'entry_id': entry.id}))
        entry = JournalEntry.objects.all()[0]
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertEqual(entry.date, datetime.date(2011, 5, 1))
        self.assertEqual(entry.memo, 'new memo!')
        self.assertEqual(Account.objects.get(name='asset').balance, 5)
        self.assertEqual(Account.objects.get(name='expense').balance, -5)

    def test_add_journal_entry_view_edit_delta_success(self):
        """
        A `POST` to the `add_journal_entry` view with a `entry_id` should
        modify the JournalEntry and it's Transactions with the POSTed data and
        redirect to the Entry's detail page.
        """
        self.test_add_journal_entry_view_success()
        entry = JournalEntry.objects.all()[0]
        response = self.client.post(
            reverse('entries.views.add_journal_entry',
                    kwargs={'entry_id': JournalEntry.objects.all()[0].id}),
            data={'entry-date': '5/1/11',
                  'entry-memo': 'new memo!',
                  'transaction-TOTAL_FORMS': 22,
                  'transaction-INITIAL_FORMS': 2,
                  'transaction-MAX_NUM_FORMS': '',
                  'transaction-0-id': Transaction.objects.all()[0].id,
                  'transaction-0-journal_entry': entry.id,
                  'transaction-0-account': self.asset_account.id,
                  'transaction-0-credit': 8,
                  'transaction-0-detail': 'debit',
                  'transaction-0-event': self.event.id,
                  'transaction-1-id': Transaction.objects.all()[1].id,
                  'transaction-1-journal_entry': entry.id,
                  'transaction-1-account': self.expense_account.id,
                  'transaction-1-debit': 8,
                  'transaction-1-detail': 'credit',
                  'subbtn': 'Submit'})
        self.assertRedirects(
            response,
            reverse('entries.views.show_journal_entry',
                    kwargs={'entry_id': entry.id}))
        entry = JournalEntry.objects.all()[0]
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertEqual(entry.date, datetime.date(2011, 5, 1))
        self.assertEqual(entry.memo, 'new memo!')
        self.assertEqual(Account.objects.get(name='asset').balance, 8)
        self.assertEqual(Account.objects.get(name='expense').balance, -8)

    def test_add_journal_entry_view_edit_account_and_delta_success(self):
        """
        A `POST` to the `add_journal_entry` view with a `entry_id` should
        modify the JournalEntry and it's Transactions with the POSTed data and
        redirect to the Entry's detail page.
        """
        self.test_add_journal_entry_view_success()
        entry = JournalEntry.objects.all()[0]
        response = self.client.post(
            reverse('entries.views.add_journal_entry',
                    kwargs={'entry_id': JournalEntry.objects.all()[0].id}),
            data={'entry-date': '5/1/11',
                  'entry-memo': 'new memo!',
                  'transaction-TOTAL_FORMS': 22,
                  'transaction-INITIAL_FORMS': 2,
                  'transaction-MAX_NUM_FORMS': '',
                  'transaction-0-id': Transaction.objects.all()[0].id,
                  'transaction-0-journal_entry': entry.id,
                  'transaction-0-account': self.expense_account.id,
                  'transaction-0-debit': 8,
                  'transaction-0-detail': 'debit',
                  'transaction-1-id': Transaction.objects.all()[1].id,
                  'transaction-1-journal_entry': entry.id,
                  'transaction-1-account': self.asset_account.id,
                  'transaction-1-credit': 8,
                  'transaction-1-detail': 'credit',
                  'transaction-1-event': self.event.id,
                  'subbtn': 'Submit'})
        self.assertRedirects(response,
                             reverse('entries.views.show_journal_entry',
                                     kwargs={'entry_id': entry.id}))
        entry = JournalEntry.objects.all()[0]
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertEqual(entry.date, datetime.date(2011, 5, 1))
        self.assertEqual(entry.memo, 'new memo!')
        self.assertEqual(Account.objects.get(name='asset').balance, 8)
        self.assertEqual(Account.objects.get(name='expense').balance, -8)
        self.assertEqual(
            Transaction.objects.get(account=self.expense_account).event,
            None)
        self.assertEqual(
            Transaction.objects.get(account=self.asset_account).event,
            self.event)

    def test_add_journal_entry_view_edit_new_transactions_success(self):
        """
        A `POST` to the `add_journal_entry` view with a `entry_id` should
        modify the JournalEntry and it's Transactions with the POSTed data and
        redirect to the Entry's detail page.
        """
        self.test_add_journal_entry_view_success()
        entry = JournalEntry.objects.all()[0]
        response = self.client.post(
            reverse('entries.views.add_journal_entry',
                    kwargs={'entry_id': JournalEntry.objects.all()[0].id}),
            data={'entry-date': '5/1/11',
                  'entry-memo': 'new memo!',
                  'transaction-TOTAL_FORMS': 22,
                  'transaction-INITIAL_FORMS': 2,
                  'transaction-MAX_NUM_FORMS': '',
                  'transaction-0-id': Transaction.objects.all()[0].id,
                  'transaction-0-journal_entry': entry.id,
                  'transaction-0-account': self.asset_account.id,
                  'transaction-0-debit': 8,
                  'transaction-0-detail': 'debit',
                  'transaction-0-event': self.event.id,
                  'transaction-1-id': Transaction.objects.all()[1].id,
                  'transaction-1-journal_entry': entry.id,
                  'transaction-1-account': self.expense_account.id,
                  'transaction-1-credit': 5,
                  'transaction-1-detail': 'credit',
                  'transaction-2-id': '',
                  'transaction-2-journal_entry': entry.id,
                  'transaction-2-account': self.asset_account.id,
                  'transaction-2-credit': 3,
                  'subbtn': 'Submit'})
        self.assertRedirects(
            response,
            reverse('entries.views.show_journal_entry',
                    kwargs={'entry_id': entry.id}))
        entry = JournalEntry.objects.all()[0]
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 3)
        self.assertEqual(entry.date, datetime.date(2011, 5, 1))
        self.assertEqual(entry.memo, 'new memo!')
        self.assertEqual(Account.objects.get(name='asset').balance, -5)
        self.assertEqual(Account.objects.get(name='expense').balance, 5)

    def test_add_journal_entry_edit_account_n_balance_change_new_success(self):
        """
        A `POST` to the `add_journal_entry` view with a `entry_id` should
        modify the JournalEntry and it's Transactions with the POSTed data and
        redirect to the Entry's detail page.

        This Test tests changing both accounts and balances and adding new
        transactions.
        """
        self.test_add_journal_entry_view_success()
        entry = JournalEntry.objects.all()[0]
        response = self.client.post(
            reverse('entries.views.add_journal_entry',
                    kwargs={'entry_id': JournalEntry.objects.all()[0].id}),
            data={'entry-date': '5/1/11',
                  'entry-memo': 'new memo!',
                  'transaction-TOTAL_FORMS': 22,
                  'transaction-INITIAL_FORMS': 2,
                  'transaction-MAX_NUM_FORMS': '',
                  'transaction-0-id': Transaction.objects.all()[0].id,
                  'transaction-0-journal_entry': entry.id,
                  'transaction-0-account': self.expense_account.id,
                  'transaction-0-credit': 8,
                  'transaction-0-detail': 'debit',
                  'transaction-0-event': self.event.id,
                  'transaction-1-id': Transaction.objects.all()[1].id,
                  'transaction-1-journal_entry': entry.id,
                  'transaction-1-account': self.asset_account.id,
                  'transaction-1-credit': 10,
                  'transaction-1-detail': 'credit',
                  'transaction-2-id': '',
                  'transaction-2-journal_entry': entry.id,
                  'transaction-2-account': self.expense_account.id,
                  'transaction-2-debit': 18,
                  'subbtn': 'Submit'})
        self.assertRedirects(
            response,
            reverse('entries.views.show_journal_entry',
                    kwargs={'entry_id': entry.id}))
        entry = JournalEntry.objects.all()[0]
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 3)
        self.assertEqual(entry.date, datetime.date(2011, 5, 1))
        self.assertEqual(entry.memo, 'new memo!')
        self.assertEqual(Account.objects.get(name='asset').balance, 10)
        self.assertEqual(Account.objects.get(name='expense').balance, -10)

    def test_add_journal_entry_view_post_fail(self):
        """
        A `POST` to the `add_journal_entry` view with no 'submit' value will
        return a 404.
        """
        response = self.client.post(reverse('entries.views.add_journal_entry',
                                            kwargs={'entry_id': 9001}))
        self.assertEqual(response.status_code, 404)

    def test_show_journal_entry_view(self):
        """
        A `GET` to the `show_journal_entry` view with a entry_id will retrieve
        the JournalEntry, it's Transactions, debit and credit totals and
        whether it has been updated.
        """
        entry = create_entry(datetime.date.today(), 'test memo')
        create_transaction(entry, self.asset_account, 50)
        create_transaction(entry, self.expense_account, -50)

        response = self.client.get(reverse('entries.views.show_journal_entry',
                                           kwargs={'entry_id': entry.id}))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'entries/entry_detail.html')
        self.assertEqual(response.context['journal_entry'],
                         JournalEntry.objects.all()[0])
        self.assertItemsEqual(response.context['transactions'],
                              Transaction.objects.all())
        self.assertEqual(response.context['is_updated'], False)
        self.assertEqual(response.context['credit_total'], 50)
        self.assertEqual(response.context['debit_total'], -50)

        entry.created_at = datetime.datetime(datetime.date.today().year - 20,
                                             1, 1, 1, 1, 1, tzinfo=utc)
        entry.save()
        response = self.client.get(reverse('entries.views.show_journal_entry',
                                           kwargs={'entry_id': entry.id}))
        self.assertEqual(response.context['is_updated'], True)

    def test_show_journal_entry_view_fail(self):
        """
        A `GET` to the `show_journal_entry` view with an invalid entry_id will
        return a 404.
        """
        response = self.client.get(reverse('entries.views.show_journal_entry',
                                           kwargs={'entry_id': '2343'}))
        self.assertEqual(response.status_code, 404)


class TransferEntryViewTests(TestCase):
    """
    Test TransferEntry add view
    """
    def setUp(self):
        self.asset_header = create_header('asset', cat_type=1)
        self.expense_header = create_header('expense', cat_type=6)
        self.asset_account = create_account('asset', self.asset_header, 0, 1)
        self.expense_account = create_account('expense', self.expense_header,
                                              0, 6)

    def test_transfer_add_view_initial(self):
        """
        A `GET` to the `add_transfer_entry` view should display a JournalEntry
        Form and Transfer Formset.
        """
        response = self.client.get(
            reverse('entries.views.add_transfer_entry'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'entries/entry_add.html')
        self.failUnless(isinstance(response.context['entry_form'],
                                   JournalEntryForm))
        self.assertEqual(response.context['journal_type'], "Transfer")
        self.failUnless(isinstance(response.context['transaction_formset'],
                                   TransferFormSet))

    def test_transfer_add_view_success(self):
        """
        A `POST` to the `add_transfer_entry` view should create a JournalEntry
        and related Transactions, redirecting to the Entry Detail Page.
        """
        response = self.client.post(
            reverse('entries.views.add_transfer_entry'),
            data={'entry-date': datetime.date.today(),
                  'entry-memo': 'test transfer entry',
                  'transfer-TOTAL_FORMS': 20,
                  'transfer-INITIAL_FORMS': 0,
                  'transfer-MAX_NUM_FORMS': '',
                  'transfer-0-id': '',
                  'transfer-0-journal_entry': '',
                  'transfer-0-source': self.asset_account.id,
                  'transfer-0-destination': self.expense_account.id,
                  'transfer-0-amount': 15,
                  'subbtn': 'Submit'})
        entry = JournalEntry.objects.all()[0]
        self.assertRedirects(
            response,
            reverse('entries.views.show_journal_entry',
                    kwargs={'entry_id': entry.id}))
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(Account.objects.all()[0].balance, -15)
        self.assertEqual(Account.objects.all()[1].balance, 15)

    def test_transfer_add_view_fail_entry(self):
        """
        A `POST` to the `add_transfer_entry` view with invalid Entry data
        should not create a JournalEntry or Transactions and should return any
        errors.
        """
        response = self.client.post(
            reverse('entries.views.add_transfer_entry'),
            data={'entry-date': '',
                  'entry-memo': '',
                  'transfer-TOTAL_FORMS': 20,
                  'transfer-INITIAL_FORMS': 0,
                  'transfer-MAX_NUM_FORMS': '',
                  'transfer-0-id': '',
                  'transfer-0-journal_entry': '',
                  'transfer-0-source': self.asset_account.id,
                  'transfer-0-destination': self.expense_account.id,
                  'transfer-0-amount': 15,
                  'subbtn': 'Submit'})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'entry_form', 'date',
                             'This field is required.')
        self.assertFormError(response, 'entry_form', 'memo',
                             'This field is required.')
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(Account.objects.all()[0].balance, 0)
        self.assertEqual(Account.objects.all()[1].balance, 0)

    def test_transfer_add_view_fail_no_dest(self):
        """
        A `POST` to the `add_transfer_entry` view with invalid Transaction data
        should not create a JournalEntry or Transactions and should return any
        errors.
        """
        response = self.client.post(
            reverse('entries.views.add_transfer_entry'),
            data={'entry-date': datetime.date.today(),
                  'entry-memo': 'test transfer entry',
                  'transfer-TOTAL_FORMS': 20,
                  'transfer-INITIAL_FORMS': 0,
                  'transfer-MAX_NUM_FORMS': '',
                  'transfer-0-id': '',
                  'transfer-0-journal_entry': '',
                  'transfer-0-source': 1,
                  'transfer-0-destination': '',
                  'transfer-0-amount': '',
                  'subbtn': 'Submit'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['transaction_formset'].forms[0].errors[
                'amount'],
            ['This field is required.'])
        self.assertEqual(
            response.context['transaction_formset'].forms[0].errors[
                'destination'],
            ['This field is required.'])
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(Account.objects.all()[0].balance, 0)
        self.assertEqual(Account.objects.all()[1].balance, 0)

    def test_transfer_add_view_fail_transactions_empty(self):
        """
        A `POST` to the `add_transfer_entry` view with no Transaction data
        should not create a JournalEntry or Transactions and should return any
        errors.
        refs #88: Empty Entries are Allowed to be Submit
        """
        response = self.client.post(
            reverse('entries.views.add_transfer_entry'),
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
        self.assertEqual(
            response.context['transaction_formset'].non_form_errors()[0],
            "At least one Transaction is required to create an Entry.")
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(Account.objects.all()[0].balance, 0)
        self.assertEqual(Account.objects.all()[1].balance, 0)


class BankEntryViewTests(TestCase):
    """
    Test the BankSpendingEntry and BankReceivingEntry add and detail views
    """
    def setUp(self):
        """
        Bank Entries require a Bank Account(Assets) and a normal Account(assume
        Expense)
        """
        self.asset_header = create_header('asset', cat_type=1)
        self.expense_header = create_header('expense', cat_type=6)
        self.bank_account = create_account('bank', self.asset_header, 0, 1,
                                           True)
        self.expense_account = create_account('expense', self.expense_header,
                                              0, 6)

    def test_bank_receiving_add_view_initial(self):
        """
        A `GET` to the `add_bank_entry` view with a `journal_type` of `CR`
        should display BankReceving Forms and Formsets.
        """
        response = self.client.get(reverse('entries.views.add_bank_entry',
                                           kwargs={'journal_type': 'CR'}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'entries/entry_add.html')
        self.failUnless(isinstance(response.context['entry_form'],
                                   BankReceivingForm))
        self.assertEqual(response.context['journal_type'], 'CR')
        self.failUnless(isinstance(response.context['transaction_formset'],
                                   BankReceivingTransactionFormSet))

    def test_bank_receiving_add_view_success(self):
        """
        A `POST` to the 'add_bank_entry' view with a `journal_type` of `CR`
        should create a new BankReceivingEntry and issue a redirect.
        """
        response = self.client.post(
            reverse('entries.views.add_bank_entry',
                    kwargs={'journal_type': 'CR'}),
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
        entry = BankReceivingEntry.objects.all()[0]
        self.assertRedirects(
            response,
            reverse('entries.views.show_bank_entry',
                    kwargs={'journal_type': 'CR', 'entry_id': entry.id}))
        self.assertEqual(BankReceivingEntry.objects.count(), 1)
        self.assertEqual(Account.objects.get(bank=True).balance, -20)
        self.assertEqual(Account.objects.get(bank=False).balance, 20)

    def test_bank_receiving_add_view_failure_entry(self):
        """
        A `POST` to the `add_bank_entry` view with a journal type of `CR` with
        invalid entry data will not create a BankReceivingEntry and displays
        an error message.
        """
        response = self.client.post(
            reverse('entries.views.add_bank_entry',
                    kwargs={'journal_type': 'CR'}),
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
        self.assertFormError(response, 'entry_form', 'payor',
                             'This field is required.')
        self.assertEqual(BankReceivingEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_bank_receiving_add_view_failure_transaction(self):
        """
        A `POST` to the `add_bank_entry` view with a journal type of `CR` with
        invalid transaction data will not create a BankReceivingEntry and
        displays an error message.
        """
        response = self.client.post(
            reverse('entries.views.add_bank_entry',
                    kwargs={'journal_type': 'CR'}),
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
        self.assertEqual(
            response.context['transaction_formset'].non_form_errors()[0],
            "The Entry Amount must equal the total Transaction Amount.")
        self.assertEqual(BankReceivingEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_bank_receiving_add_view_add_another(self):
        """
        A `POST` to the 'add_bank_entry' view with a `journal_type` of `CR` and
        submit value of `Submit & Add Another` should create a new
        BankReceivingEntry and issue redirect back to the Add page,
        initializing the entry form with last Entries bank_account.
        """
        response = self.client.post(
            reverse('entries.views.add_bank_entry',
                    kwargs={'journal_type': 'CR'}),
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

        self.assertRedirects(
            response,
            (reverse('entries.views.add_bank_entry',
                     kwargs={'journal_type': 'CR'}
                     ) + '?bank_account={0}'.format(self.bank_account.id))
        )
        response = self.client.get(response._headers['location'][1])
        self.assertEqual(response.context['entry_form'].initial['account'],
                         str(self.bank_account.id))
        self.assertEqual(BankReceivingEntry.objects.count(), 1)
        self.assertEqual(Account.objects.get(bank=True).balance, -20)
        self.assertEqual(Account.objects.get(bank=False).balance, 20)

    def test_bank_receiving_add_view_delete(self):
        """
        A `POST` to the `add_bank_entry` view with a `entry_id` and
        `journal_type` of 'CR' will delete the BankReceivingEntry and all
        related Transactions, refunding the respective Accounts.
        """
        self.test_bank_receiving_add_view_success()
        entry = BankReceivingEntry.objects.all()[0]

        self.assertEqual(BankReceivingEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertEqual(Account.objects.get(name='bank').balance, -20)
        self.assertEqual(Account.objects.get(name='expense').balance, 20)

        response = self.client.post(reverse('entries.views.add_bank_entry',
                                            kwargs={'entry_id': entry.id,
                                                    'journal_type': 'CR'}),
                                    data={'delete': 'Delete'})

        self.assertRedirects(
            response,
            reverse('accounts.views.bank_journal',
                    kwargs={'account_slug': self.bank_account.slug})
        )
        self.assertEqual(BankReceivingEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(Account.objects.get(name='bank').balance, 0)
        self.assertEqual(Account.objects.get(name='expense').balance, 0)

    def test_bank_receiving_add_view_delete_fail(self):
        """
        A `POST` to the `add_bank_entry` view with an invalid `entry_id` and
        `journal_type` of 'CR' will return a 404.
        """
        self.assertEqual(BankReceivingEntry.objects.count(), 0)
        response = self.client.post(reverse('entries.views.add_bank_entry',
                                            kwargs={'entry_id': 9001,
                                                    'journal_type': 'CR'}),
                                    data={'delete': 'Delete'})
        self.assertEqual(response.status_code, 404)

    def test_bank_receiving_add_view_edit(self):
        """
        A `GET` to the `add_bank_entry` view with a `journal_type` of `CR` and
        a `entry_id` should display BankReceiving Forms and Formsets using an
        instance of the BankReceivingEntry with id `entry_id` if there is
        no current FiscalYear.
        """
        self.test_bank_receiving_add_view_success()
        entry = BankReceivingEntry.objects.all()[0]
        response = self.client.get(reverse('entries.views.add_bank_entry',
                                           kwargs={'journal_type': 'CR',
                                                   'entry_id': entry.id}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'entries/entry_add.html')
        self.failUnless(isinstance(response.context['entry_form'],
                                   BankReceivingForm))
        self.failUnless(isinstance(response.context['transaction_formset'],
                                   BankReceivingTransactionFormSet))
        self.assertEqual(response.context['entry_form'].instance, entry)
        self.assertEqual(response.context['entry_form'].initial['amount'],
                         -1 * entry.main_transaction.balance_delta)
        self.assertEqual(response.context['entry_form'].initial['account'],
                         entry.main_transaction.account)
        self.assertEqual(
            response.context['transaction_formset'].forms[0].instance,
            entry.transaction_set.all()[0])
        self.assertEqual(
            response.context['transaction_formset'].forms[0].initial['amount'],
            entry.transaction_set.all()[0].balance_delta)

    def test_bank_receiving_add_view_edit_success(self):
        """
        A `POST` to the 'add_bank_entry' view with a `journal_type` of `CR`
        with a `entry_id` should edit the respective BankReceivingEntry and
        issue a redirect.
        """
        self.test_bank_receiving_add_view_success()
        entry = BankReceivingEntry.objects.all()[0]
        new_bank_account = create_account('2nd bank', self.asset_header, 0, 1,
                                          True)
        new_expense_account = create_account('2nd expense',
                                             self.expense_header, 0, 6)
        response = self.client.post(
            reverse('entries.views.add_bank_entry',
                    kwargs={'journal_type': 'CR',
                            'entry_id': entry.id}),
            data={'entry-account': new_bank_account.id,
                  'entry-date': '4/20/1999',
                  'entry-payor': 'new payor',
                  'entry-amount': 20,
                  'entry-memo': 'new memo',
                  'transaction-TOTAL_FORMS': 20,
                  'transaction-INITIAL_FORMS': 1,
                  'transaction-MAX_NUM_FORMS': '',
                  'transaction-0-id': Transaction.objects.all()[1].id,
                  'transaction-0-bankreceive_entry': entry.id,
                  'transaction-0-detail': 'test detail',
                  'transaction-0-amount': 15,
                  'transaction-0-account': new_expense_account.id,
                  'transaction-1-id': '',
                  'transaction-1-bankreceive_entry': entry.id,
                  'transaction-1-detail': 'test detail 2',
                  'transaction-1-amount': 5,
                  'transaction-1-account': self.expense_account.id,
                  'subbtn': 'Submit',
                  })
        self.assertRedirects(response, reverse('entries.views.show_bank_entry',
                                               kwargs={'journal_type': 'CR',
                                                       'entry_id': entry.id}))
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
        self.assertEqual(new_bank_account,
                         Transaction.objects.all()[0].account)
        self.assertEqual(new_expense_account,
                         Transaction.objects.all()[1].account)
        self.assertEqual(self.expense_account,
                         Transaction.objects.all()[2].account)

    def test_bank_receiving_add_view_edit_in_fiscal_year(self):
        """
        A `GET` to the `add_bank_entry` view with a `journal_type` of `CR` and
        a `entry_id` should display BankReceiving Forms and Formsets using an
        instance of the BankReceivingEntry with id `entry_id` if the `date`
        is in the current FiscalYear.
        """
        FiscalYear.objects.create(year=2013, end_month=12, period=12)
        self.test_bank_receiving_add_view_success()
        entry = BankReceivingEntry.objects.all()[0]
        response = self.client.get(reverse('entries.views.add_bank_entry',
                                           kwargs={'journal_type': 'CR',
                                                   'entry_id': entry.id}))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'entries/entry_add.html')

    def test_bank_receiving_add_view_edit_out_of_fiscal_year(self):
        """
        A `GET` to the `add_journal_entry` view with a `entry_id` will return
        a 404 Error if the entry is before the current Fiscal Year.
        """
        self.test_bank_receiving_add_view_success()
        FiscalYear.objects.create(year=2015, end_month=12, period=12)
        entry = BankReceivingEntry.objects.all()[0]
        response = self.client.get(reverse('entries.views.add_bank_entry',
                                           kwargs={'journal_type': 'CR',
                                                   'entry_id': entry.id}))

        self.assertEqual(response.status_code, 404)

    def test_bank_receiving_add_view_fiscal_year(self):
        """
        A `POST` to the ``add_bank_entry`` view with a ``journal_type`` of
        ``CR`` and a ``date`` on or after the start of the current
        ``FiscalYear`` will create a BankReceivingEntry and Transactions.
        If there is only one FiscalYear, the ``period`` amount of months before
        the ``end_month`` is used.
        """
        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        response = self.client.post(
            reverse('entries.views.add_bank_entry',
                    kwargs={'journal_type': 'CR'}),
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
        entry = BankReceivingEntry.objects.all()[0]
        self.assertRedirects(
            response,
            reverse('entries.views.show_bank_entry',
                    kwargs={'journal_type': 'CR', 'entry_id': entry.id}))
        self.assertEqual(BankReceivingEntry.objects.count(), 1)
        self.assertEqual(Account.objects.get(bank=True).balance, -20)
        self.assertEqual(Account.objects.get(bank=False).balance, 20)

    def test_bank_receiving_add_view_fail_fiscal_year(self):
        """
        A `POST` to the ``add_bank_entry`` view with a ``journal_type`` of
        ``CR`` and a ``date`` before the start of the current ``FiscalYear``
        will not create a BankReceivingEntry or Transactions and displays an
        error message.
        If there is only one FiscalYear, the ``period`` amount of months before
        the ``end_month`` is used.
        """
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        response = self.client.post(
            reverse('entries.views.add_bank_entry',
                    kwargs={'journal_type': 'CR'}),
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
        self.assertFormError(
            response, 'entry_form', 'date',
            'The date must be in the current Fiscal Year.')
        self.assertEqual(BankReceivingEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_bank_receiving_add_view_two_fiscal_year(self):
        """
        A `POST` to the ``add_bank_entry`` view with a ``journal_type`` of
        ``CR`` and a ``date`` on or after the start of the current
        ``FiscalYear`` will create a BankReceivingEntry and Transactions.
        If there is are multiple FiscalYear, the ``date`` cannot be before the
        ``end_month`` of the Second to Latest FiscalYear.
        """
        FiscalYear.objects.create(year=2010, end_month=12, period=12)
        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        response = self.client.post(
            reverse('entries.views.add_bank_entry',
                    kwargs={'journal_type': 'CR'}),
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
        entry = BankReceivingEntry.objects.all()[0]
        self.assertRedirects(
            response,
            reverse('entries.views.show_bank_entry',
                    kwargs={'journal_type': 'CR', 'entry_id': entry.id}))
        self.assertEqual(BankReceivingEntry.objects.count(), 1)
        self.assertEqual(Account.objects.get(bank=True).balance, -20)
        self.assertEqual(Account.objects.get(bank=False).balance, 20)

    def test_bank_receiving_add_view_fail_two_fiscal_year(self):
        """
        A `POST` to the ``add_bank_entry`` view with a ``journal_type`` of
        ``CR`` and a ``date`` before the start of the current ``FiscalYear``
        will not create a BankReceivingEntry or Transactions and displays an
        error message.
        If there is are multiple FiscalYear, the ``date`` cannot be before the
        ``end_month`` of the Second to Latest FiscalYear.
        """
        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        response = self.client.post(
            reverse('entries.views.add_bank_entry',
                    kwargs={'journal_type': 'CR'}),
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
        self.assertFormError(
            response, 'entry_form', 'date',
            'The date must be in the current Fiscal Year.')
        self.assertEqual(BankReceivingEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_bank_receiving_add_view_post_fail(self):
        """
        A `POST` to the `add_bank_entry` view with no submit value will return
        a 404.
        """
        response = self.client.post(reverse('entries.views.add_bank_entry',
                                            kwargs={'entry_id': 9001,
                                                    'journal_type': 'CR'}))
        self.assertEqual(response.status_code, 404)

    def test_bank_receiving_show_view(self):
        """
        A `GET` to the `show_bank_entry` view with a journal type of `CD` and a
        entry_id will retrieve a BankReceivingEntry passing the respective
        journal_entry, main_transaction and transaction set
        """
        self.test_bank_receiving_add_view_success()
        entry = BankReceivingEntry.objects.all()[0]
        response = self.client.get(reverse('entries.views.show_bank_entry',
                                           kwargs={'journal_type': 'CR',
                                                   'entry_id': entry.id}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response,
                                'entries/entry_bankreceive_detail.html')
        self.failUnless(isinstance(response.context['journal_entry'],
                                   BankReceivingEntry))
        self.assertEqual(BankReceivingEntry.objects.all()[0],
                         response.context['journal_entry'])
        self.assertItemsEqual(
            response.context['journal_entry'].transaction_set.all(),
            response.context['transactions'])
        self.assertEqual(
            response.context['journal_entry'].main_transaction,
            response.context['main_transaction'])

    def test_bank_spending_add_view_initial(self):
        """
        A `GET` to the `add_bank_entry` view with a `journal_type` of `CD`
        should display BankSpending Forms and Formsets.
        """
        response = self.client.get(reverse('entries.views.add_bank_entry',
                                           kwargs={'journal_type': 'CD'}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'entries/entry_add.html')
        self.failUnless(isinstance(response.context['entry_form'],
                                   BankSpendingForm))
        self.assertEqual(response.context['journal_type'], 'CD')
        self.failUnless(isinstance(response.context['transaction_formset'],
                                   BankSpendingTransactionFormSet))

    def test_bank_spending_add_view_success(self):
        """
        A `POST` to the 'add_bank_entry' view with a `journal_type` of `CD`
        should create a new BankSpendingEntry and issue a redirect.
        """
        response = self.client.post(
            reverse('entries.views.add_bank_entry',
                    kwargs={'journal_type': 'CD'}),
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
        entry = BankSpendingEntry.objects.all()[0]
        self.assertRedirects(response, reverse('entries.views.show_bank_entry',
                                               kwargs={'journal_type': 'CD',
                                                       'entry_id': entry.id}))
        self.assertEqual(BankSpendingEntry.objects.count(), 1)
        self.assertEqual(Account.objects.get(bank=True).balance, 20)
        self.assertEqual(Account.objects.get(bank=False).balance, -20)

    def test_bank_spending_add_view_failure_entry(self):
        """
        A `POST` to the `add_bank_entry` view with a journal type of `CD` with
        invalid entry data will not create a BankSpendingEntry and displays
        an error message.
        """
        response = self.client.post(
            reverse('entries.views.add_bank_entry',
                    kwargs={'journal_type': 'CD'}),
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
        self.assertFormError(response, 'entry_form', None,
                             'Either A Check Number or ACH status is '
                             'required.')
        self.assertEqual(BankSpendingEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_bank_spending_add_view_failure_transaction(self):
        """
        A `POST` to the `add_bank_entry` view with a journal type of `CD` with
        invalid transaction data will not create a BankSpendingEntry and
        displays an error message.
        """
        response = self.client.post(
            reverse('entries.views.add_bank_entry',
                    kwargs={'journal_type': 'CD'}),
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
        self.assertEqual(
            response.context['transaction_formset'].non_form_errors()[0],
            "The Entry Amount must equal the total Transaction Amount.")
        self.assertEqual(BankSpendingEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_bank_spending_add_view_add_another(self):
        """
        A `POST` to the 'add_bank_entry' view with a `journal_type` of `CD` and
        submit value of `Submit & Add Another` should create a new
        BankSpendingEntry and issue redirect back to the Add page, initializing
        the entry form with last Entries bank_account.
        """
        response = self.client.post(
            reverse('entries.views.add_bank_entry',
                    kwargs={'journal_type': 'CD'}),
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

        self.assertRedirects(
            response,
            (reverse('entries.views.add_bank_entry',
                     kwargs={'journal_type': 'CD'}) +
             '?bank_account={0}'.format(self.bank_account.id))
        )
        response = self.client.get(response._headers['location'][1])
        self.assertEqual(response.context['entry_form'].initial['account'],
                         str(self.bank_account.id))
        self.assertEqual(BankSpendingEntry.objects.count(), 1)
        self.assertEqual(Account.objects.get(bank=True).balance, 20)
        self.assertEqual(Account.objects.get(bank=False).balance, -20)

    def test_bank_spending_add_view_delete(self):
        """
        A `POST` to the `add_bank_entry` view with a `entry_id` and
        `journal_type` of 'CD' will delete the BankSpendingEntry and all
        related Transactions, refunding the respective Accounts.
        """
        self.test_bank_spending_add_view_success()
        entry = BankSpendingEntry.objects.all()[0]

        self.assertEqual(BankSpendingEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertEqual(Account.objects.get(name='bank').balance, 20)
        self.assertEqual(Account.objects.get(name='expense').balance, -20)

        response = self.client.post(reverse('entries.views.add_bank_entry',
                                            kwargs={'entry_id': entry.id,
                                                    'journal_type': 'CD'}),
                                    data={'delete': 'Delete'})

        self.assertRedirects(
            response,
            reverse('accounts.views.bank_journal',
                    kwargs={'account_slug': self.bank_account.slug})
        )
        self.assertEqual(BankSpendingEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(Account.objects.get(name='bank').balance, 0)
        self.assertEqual(Account.objects.get(name='expense').balance, 0)

    def test_bank_spending_add_view_delete_fail(self):
        """
        A `POST` to the `add_bank_entry` view with an invalid `entry_id` and
        `journal_type` of 'CD' will return a 404
        """
        self.assertEqual(BankSpendingEntry.objects.count(), 0)
        response = self.client.post(reverse('entries.views.add_bank_entry',
                                            kwargs={'entry_id': 9001,
                                                    'journal_type': 'CD'}),
                                    data={'delete': 'Delete'})
        self.assertEqual(response.status_code, 404)

    def test_bank_spending_add_view_edit(self):
        """
        A `GET` to the `add_bank_entry` view with a `journal_type` of `CD` and
        a `entry_id` should display BankSpending Forms and Formsets editing
        the BankSpendingEntry with id of `entry_id`.
        """
        self.test_bank_spending_add_view_success()
        entry = BankSpendingEntry.objects.all()[0]
        response = self.client.get(reverse('entries.views.add_bank_entry',
                                           kwargs={'journal_type': 'CD',
                                                   'entry_id': entry.id}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'entries/entry_add.html')
        self.failUnless(isinstance(response.context['entry_form'],
                                   BankSpendingForm))
        self.failUnless(isinstance(response.context['transaction_formset'],
                                   BankSpendingTransactionFormSet))
        self.assertEqual(response.context['entry_form'].instance, entry)
        self.assertEqual(response.context['entry_form'].initial['amount'],
                         entry.main_transaction.balance_delta)
        self.assertEqual(response.context['entry_form'].initial['account'],
                         entry.main_transaction.account)
        self.assertEqual(
            response.context['transaction_formset'].forms[0].instance,
            entry.transaction_set.all()[0])
        self.assertEqual(
            response.context['transaction_formset'].forms[0].initial['amount'],
            -1 * entry.transaction_set.all()[0].balance_delta)

    def test_bank_spending_add_view_edit_in_fiscal_year(self):
        """
        A `GET` to the `add_bank_entry` view with a `journal_type` of `CD` and
        a `entry_id` should display BankSpending Forms and Formsets editing
        the BankSpendingEntry with id of `entry_id` if the `date`
        is in the current FiscalYear.
        """
        FiscalYear.objects.create(year=2013, end_month=12, period=12)
        self.test_bank_spending_add_view_success()
        entry = BankSpendingEntry.objects.all()[0]
        response = self.client.get(reverse('entries.views.add_bank_entry',
                                           kwargs={'journal_type': 'CD',
                                                   'entry_id': entry.id}))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'entries/entry_add.html')

    def test_bank_spending_add_view_edit_out_of_fiscal_year(self):
        """
        A `GET` to the `add_bank_entry` view with a `journal_type` of `CD` and
        a `entry_id` will return a 404 Error if the entry is before the
        current Fiscal Year.
        """
        self.test_bank_spending_add_view_success()
        FiscalYear.objects.create(year=2015, end_month=12, period=12)
        entry = BankSpendingEntry.objects.all()[0]
        response = self.client.get(reverse('entries.views.add_bank_entry',
                                           kwargs={'journal_type': 'CD',
                                                   'entry_id': entry.id}))

        self.assertEqual(response.status_code, 404)

    def test_bank_spending_add_view_edit_success(self):
        """
        A `POST` to the 'add_bank_entry' view with a `journal_type` of `CD`
        with a `entry_id` should edit the respective BankSpendingEntry and
        issue a redirect.
        """
        self.test_bank_spending_add_view_success()
        entry = BankSpendingEntry.objects.all()[0]
        new_bank_account = create_account('2nd bank', self.asset_header, 0, 1,
                                          True)
        new_expense_account = create_account('2nd expense',
                                             self.expense_header, 0, 6)
        response = self.client.post(
            reverse('entries.views.add_bank_entry',
                    kwargs={'journal_type': 'CD',
                            'entry_id': entry.id}),
            data={'entry-account': new_bank_account.id,
                  'entry-date': '12/12/12',
                  'entry-check_number': 2177,
                  'entry-payee': 'new payee',
                  'entry-amount': 20,
                  'entry-memo': 'new memo',
                  'transaction-TOTAL_FORMS': 20,
                  'transaction-INITIAL_FORMS': 1,
                  'transaction-MAX_NUM_FORMS': '',
                  'transaction-0-id': Transaction.objects.all()[1].id,
                  'transaction-0-bankspend_entry': entry.id,
                  'transaction-0-detail': 'test detail',
                  'transaction-0-amount': 15,
                  'transaction-0-account': new_expense_account.id,
                  'transaction-1-id': '',
                  'transaction-1-bankspend_entry': entry.id,
                  'transaction-1-detail': 'test detail 2',
                  'transaction-1-amount': 5,
                  'transaction-1-account': self.expense_account.id,
                  'subbtn': 'Submit',
                  })
        self.assertRedirects(
            response,
            reverse('entries.views.show_bank_entry',
                    kwargs={'journal_type': 'CD', 'entry_id': entry.id}))
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
        self.assertEqual(new_bank_account,
                         Transaction.objects.all()[0].account)
        self.assertEqual(new_expense_account,
                         Transaction.objects.all()[1].account)

    def test_bank_spending_add_view_fiscal_year(self):
        """
        A `POST` to the ``add_bank_entry`` view with a ``journal_type`` of
        ``CD`` and a ``date`` on or after the start of the current
        ``FiscalYear`` will create a BankReceivingEntry and Transactions.
        If there is only one FiscalYear, the ``period`` amount of months before
        the ``end_month`` is used.
        """
        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        response = self.client.post(
            reverse('entries.views.add_bank_entry',
                    kwargs={'journal_type': 'CD'}),
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
        entry = BankSpendingEntry.objects.all()[0]
        self.assertRedirects(
            response,
            reverse('entries.views.show_bank_entry',
                    kwargs={'journal_type': 'CD', 'entry_id': entry.id}))
        self.assertEqual(BankSpendingEntry.objects.count(), 1)
        self.assertEqual(Account.objects.get(bank=True).balance, 20)
        self.assertEqual(Account.objects.get(bank=False).balance, -20)

    def test_bank_spending_add_view_fail_fiscal_year(self):
        """
        A `POST` to the ``add_bank_entry`` view with a ``journal_type`` of
        ``CD`` and a ``date`` before the start of the current ``FiscalYear``
        will not create a BankReceivingEntry or Transactions and displays an
        error message.
        If there is only one FiscalYear, the ``period`` amount of months before
        the ``end_month`` is used.
        """
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        response = self.client.post(
            reverse('entries.views.add_bank_entry',
                    kwargs={'journal_type': 'CR'}),
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
        self.assertFormError(
            response, 'entry_form', 'date', 'The date must be in the current '
            'Fiscal Year.')
        self.assertEqual(BankSpendingEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_bank_spending_add_view_two_fiscal_year(self):
        """
        A `POST` to the ``add_bank_entry`` view with a ``journal_type`` of
        ``CD`` and a ``date`` on or after the start of the current
        ``FiscalYear`` will create a BankReceivingEntry and Transactions.
        If there is are multiple FiscalYear, the ``date`` cannot be before the
        ``end_month`` of the Second to Latest FiscalYear.
        """
        FiscalYear.objects.create(year=2010, end_month=12, period=12)
        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        response = self.client.post(
            reverse('entries.views.add_bank_entry',
                    kwargs={'journal_type': 'CD'}),
            data={'entry-account': self.bank_account.id,
                  'entry-date': '2011-01-12',
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
        entry = BankSpendingEntry.objects.all()[0]
        self.assertRedirects(
            response,
            reverse('entries.views.show_bank_entry',
                    kwargs={'journal_type': 'CD', 'entry_id': entry.id}))
        self.assertEqual(BankSpendingEntry.objects.count(), 1)
        self.assertEqual(Account.objects.get(bank=True).balance, 20)
        self.assertEqual(Account.objects.get(bank=False).balance, -20)

    def test_bank_spending_add_view_fail_two_fiscal_year(self):
        """
        A `POST` to the ``add_bank_entry`` view with a ``journal_type`` of
        ``CD`` and a ``date`` before the start of the current ``FiscalYear``
        will not create a BankReceivingEntry or Transactions and displays an
        error message.
        If there is are multiple FiscalYear, the ``date`` cannot be before the
        ``end_month`` of the Second to Latest FiscalYear.
        """
        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        response = self.client.post(
            reverse('entries.views.add_bank_entry',
                    kwargs={'journal_type': 'CD'}),
            data={'entry-account': self.bank_account.id,
                  'entry-date': '2011-01-11',
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
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['entry_form'].is_valid())
        self.assertFormError(
            response, 'entry_form', 'date',
            'The date must be in the current Fiscal Year.')
        self.assertEqual(BankSpendingEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_bank_spending_add_view_post_fail(self):
        """
        A `POST` to the `add_bank_entry` view with no value for submit will
        return a 404.
        """
        response = self.client.post(reverse('entries.views.add_bank_entry',
                                            kwargs={'entry_id': 9001,
                                                    'journal_type': 'CD'}))
        self.assertEqual(response.status_code, 404)

    def test_bank_spending_show_view(self):
        """
        A `GET` to the `show_bank_entry` view with a journal type of `CD` and a
        entry_id will retrieve the respective BankSpendingEntry
        """
        self.test_bank_spending_add_view_success()
        entry = BankSpendingEntry.objects.all()[0]
        response = self.client.get(
            reverse('entries.views.show_bank_entry',
                    kwargs={'journal_type': 'CD', 'entry_id': entry.id}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response,
                                'entries/entry_bankspend_detail.html')
        self.failUnless(isinstance(response.context['journal_entry'],
                                   BankSpendingEntry))
        self.assertEqual(BankSpendingEntry.objects.all()[0],
                         response.context['journal_entry'])
        self.assertItemsEqual(
            response.context['journal_entry'].transaction_set.all(),
            response.context['transactions'])
        self.assertEqual(response.context['journal_entry'].main_transaction,
                         response.context['main_transaction'])


class JournalLedgerViewTests(TestCase):
    """
    Test view for showing all General Journal Entries in a time period
    """
    def setUp(self):
        self.asset_header = create_header('asset', cat_type=1)
        self.liability_header = create_header('liability', cat_type=2)
        self.bank_account = create_account('bank', self.asset_header, 0, 1,
                                           True)
        self.liability_account = create_account('liability',
                                                self.liability_header, 0, 2)

    def test_journal_ledger_view_initial(self):
        """
        A `GET` to the `journal_ledger` view should return a DateRangeForm,
        start/stopdate from 1st of Month to Today and only JournalEntries in
        this time period.
        """
        today = datetime.date.today()
        entry = create_entry(today, 'in range entry')
        another_entry = create_entry(today, 'another in range entry')
        create_entry(datetime.date(today.year + 20, 1, 1), 'future entry')
        create_entry(datetime.date(today.year - 20, 1, 1), 'past entry')

        response = self.client.get(reverse('entries.views.journal_ledger'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'entries/journal_ledger.html')
        self.failUnless(isinstance(response.context['form'], DateRangeForm))
        self.assertEqual(response.context['start_date'],
                         datetime.date(today.year, today.month, 1))
        self.assertEqual(response.context['stop_date'], today)
        self.assertSequenceEqual(response.context['journal_entries'],
                                 [entry, another_entry])

    def test_journal_ledger_view_date_success(self):
        """
        A `GET` to the `journal_ledger` view with a startdate and stopdate
        should return only JournalEntries from that time period.
        """
        today = datetime.date.today()
        date_range = (datetime.date(today.year, 4, 1),
                      datetime.date(today.year, 5, 1))
        entry = create_entry(datetime.date(today.year, 4, 20),
                             'in range entry')
        another_entry = create_entry(datetime.date(today.year, 4, 21),
                                     'another in range entry')
        create_entry(datetime.date(today.year + 20, 4, 20), 'future entry')
        create_entry(datetime.date(today.year - 20, 7, 7), 'past entry')

        response = self.client.get(reverse('entries.views.journal_ledger'),
                                   data={'startdate': date_range[0],
                                         'stopdate': date_range[1]})

        self.assertEqual(response.status_code, 200)
        self.failUnless(response.context['form'].is_bound)
        self.assertEqual(response.context['start_date'], date_range[0])
        self.assertEqual(response.context['stop_date'], date_range[1])
        self.assertSequenceEqual(response.context['journal_entries'],
                                 [entry, another_entry])

    def test_journal_ledger_view_date_fail(self):
        """
        A `GET` to the `journal_ledger` view with an invalid startdate and
        stopdate should return a bound DateRangeForm with respective errors.
        """
        response = self.client.get(reverse('entries.views.journal_ledger'),
                                   data={'startdate': 'zerocool',
                                         'stopdate': 'foobar'})
        self.assertEqual(response.status_code, 200)
        self.failUnless(response.context['form'].is_bound)
        self.assertFormError(response, 'form', 'startdate',
                             'Enter a valid date.')
        self.assertFormError(response, 'form', 'stopdate',
                             'Enter a valid date.')
