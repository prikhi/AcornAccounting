"""
Test approving of TripEntries.
"""
import datetime

from django.core.urlresolvers import reverse
from django.test import TestCase

from accounts.models import Account
from core.tests import create_header, create_account
from entries.models import JournalEntry, Transaction

from .forms import TripStoreTransactionFormSet
from .models import (StoreAccount, TripEntry, TripTransaction,
                     TripStoreTransaction)


class TripEntryModelTests(TestCase):
    """Test the TripEntry model."""

    def setUp(self):
        """Create initial Headers, Accounts, an Entry & Transactions."""
        self.liability_header = create_header('liability', cat_type=2)
        self.trip_advances = create_account(
            "Trip Advances", self.liability_header, 0)
        self.store_account = create_account(
            "Local Store Credit Account", self.liability_header, 0)
        self.store = StoreAccount.objects.create(
            name='Local Store', account=self.store_account)
        self.expense_header = create_header("expenses", None, 6)
        self.expense_account = create_account(
            "expense", self.expense_header, 0, 6)

        entry_date = datetime.date(2015, 6, 11)
        self.entry = TripEntry.objects.create(
            date=entry_date, name='Testeroni', number='42',
            total_trip_advance=100, amount=50)
        self.trans1 = TripTransaction.objects.create(
            trip_entry=self.entry, account=self.expense_account, amount=25)
        self.trans2 = TripTransaction.objects.create(
            trip_entry=self.entry, account=self.expense_account, amount=25)
        self.store_trans = TripStoreTransaction.objects.create(
            trip_entry=self.entry, store=self.store,
            account=self.expense_account, amount=25
        )

    def test_approve_creates_entry(self):
        """
        Approving a TripEntry should create a JournalEntry and Transactions &
        affect Account balances.
        """
        self.assertEqual(self.expense_account.balance, 0)
        self.assertEqual(self.trip_advances.balance, 0)
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)

        self.entry.approve_entry()
        self.expense_account = Account.objects.get(id=self.expense_account.id)
        self.assertEqual(self.expense_account.balance, -75)
        self.trip_advances = Account.objects.get(id=self.trip_advances.id)
        self.assertEqual(self.trip_advances.balance, 50)
        self.store_account = Account.objects.get(id=self.store_account.id)
        self.assertEqual(self.store_account.balance, 25)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 5)

    def test_approve_does_not_delete(self):
        """Approving a TripEntry should not delete the TripEntry."""
        self.assertEqual(TripEntry.objects.count(), 1)
        self.assertEqual(TripTransaction.objects.count(), 2)
        self.assertEqual(TripStoreTransaction.objects.count(), 1)

        self.entry.approve_entry()
        self.assertEqual(TripEntry.objects.count(), 1)
        self.assertEqual(TripTransaction.objects.count(), 2)
        self.assertEqual(TripStoreTransaction.objects.count(), 1)

    def test_get_next_entry(self):
        """The get_next_entry method should be ordered by date, then id."""
        entry_before = TripEntry.objects.create(
            date=(self.entry.date - datetime.timedelta(days=1)),
            name='Towelie', number='42A', total_trip_advance=50, amount=50)
        entry_same1 = TripEntry.objects.create(
            date=self.entry.date, name='Towelie', number='42C',
            total_trip_advance=50, amount=50)
        entry_same2 = TripEntry.objects.create(
            date=self.entry.date, name='Towelie', number='42D',
            total_trip_advance=50, amount=50)
        entry_after = TripEntry.objects.create(
            date=(self.entry.date + datetime.timedelta(days=1)),
            name='Towelie', number='42E', total_trip_advance=50, amount=50)

        self.assertEqual(entry_before.get_next_entry().exists(), True)
        self.assertEqual(entry_before.get_next_entry()[0],
                         self.entry)
        self.assertEqual(self.entry.get_next_entry().exists(), True)
        self.assertEqual(self.entry.get_next_entry()[0],
                         entry_same1)
        self.assertEqual(entry_same1.get_next_entry().exists(), True)
        self.assertEqual(entry_same1.get_next_entry()[0],
                         entry_same2)
        self.assertEqual(entry_same2.get_next_entry().exists(), True)
        self.assertEqual(entry_same2.get_next_entry()[0],
                         entry_after)
        self.assertEqual(entry_after.get_next_entry().exists(), False)


class AddTripEntryViewTests(TestCase):
    """Test the AddTripEntryView."""

    def test_store_transactions_in_context(self):
        """A store_transaction_formset should be included in the context."""
        response = self.client.get(reverse('trips.views.add_trip_entry'))
        self.assertIn('store_transaction_formset', response.context)
        formset = response.context['store_transaction_formset']
        self.assertIsInstance(formset, TripStoreTransactionFormSet)
        self.assertFalse(formset.is_bound)

    def test_store_transactions_in_context_post(self):
        response = self.client.post(
            reverse('add_trip_entry'),
            data={'transaction-TOTAL_FORMS': 5,
                  'transaction-INITIAL_FORMS': 0,
                  'transaction-MAX_NUM_FORMS': '',
                  'store-transaction-TOTAL_FORMS': 5,
                  'store-transaction-INITIAL_FORMS': 0,
                  'store-transaction-MAX_NUM_FORMS': '',
                  'subbtn': 'Submit'})
        self.assertIn('store_transaction_formset', response.context)
        formset = response.context['store_transaction_formset']
        self.assertIsInstance(formset, TripStoreTransactionFormSet)
        self.assertTrue(formset.is_bound)
