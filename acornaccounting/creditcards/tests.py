"""
Test Creating & Approving CreditCardEntries.
"""
import datetime

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.urlresolvers import reverse
from django.test import TestCase

from accounts.models import Account
from core.tests import create_header, create_account, create_and_login_user
from entries.models import JournalEntry, Transaction

from .forms import CreditCardEntryForm, CreditCardTransactionFormSet
from .models import CreditCard, CreditCardEntry, CreditCardTransaction


class CreditCardModelTests(TestCase):
    """Test the CreditCard model."""
    def setUp(self):
        """Create an initial Account."""
        self.header = create_header("Credit Cards", None, 2)
        self.account = create_account("Darmok's CC", self.header, 0, 2)

    def test_name_defaults_to_account_name(self):
        """If the name is left blank it should be filled using the Account."""
        credit_card = CreditCard(account=self.account)
        self.assertEqual(credit_card.name, '')

        credit_card.save()
        self.assertEqual(credit_card.name, self.account.name)


class AddCreditCardPurchaseViewTests(TestCase):
    """Test the add_creditcard_entry view."""
    def setUp(self):
        """Create an initial Account & CreditCard."""
        self.liability_header = create_header('liability', cat_type=2)
        self.cc_account = create_account(
            "Credit Card", self.liability_header, 0)
        self.creditcard = CreditCard.objects.create(account=self.cc_account)
        self.expense_header = create_header("expenses", None, 6)
        self.expense_account = create_account(
            "expense", self.expense_header, 0, 6)

    def test_initial(self):
        """
        A `GET` should display a CreditCardEntry Form & a CreditCardTransaction
        Formset.
        """
        response = self.client.get(
            reverse('creditcards.views.add_creditcard_entry'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'creditcards/credit_card_form.html')
        self.failUnless(isinstance(response.context['entry_form'],
                                   CreditCardEntryForm))
        self.failUnless(isinstance(response.context['transaction_formset'],
                                   CreditCardTransactionFormSet))

    def test_success(self):
        """
        A `POST` with valid data will create a CreditCardEntry and it's
        respective Transactions.
        """
        response = self.client.post(
            reverse('creditcards.views.add_creditcard_entry'),
            data={'entry-date': '2015-04-12',
                  'entry-name': 'test anarch',
                  'entry-merchant': 'test vendor',
                  'entry-amount': 20,
                  'entry-card': self.creditcard.id,
                  'transaction-TOTAL_FORMS': 5,
                  'transaction-INITIAL_FORMS': 0,
                  'transaction-MAX_NUM_FORMS': '',
                  'transaction-0-id': '',
                  'transaction-0-creditcard_entry': '',
                  'transaction-0-detail': 'test detail',
                  'transaction-0-amount': 10,
                  'transaction-0-account': self.expense_account.id,
                  'transaction-1-id': '',
                  'transaction-1-creditcard_entry': '',
                  'transaction-1-detail': 'test detail 2',
                  'transaction-1-amount': 10,
                  'transaction-1-account': self.expense_account.id,
                  'subbtn': 'Submit'})
        self.assertEqual(CreditCardEntry.objects.count(), 1)
        self.assertEqual(CreditCardTransaction.objects.count(), 2)
        entry = CreditCardEntry.objects.all()[0]
        self.assertRedirects(
            response,
            reverse('creditcards.views.show_creditcard_entry',
                    kwargs={'entry_id': entry.id}))

    def test_success_does_not_change_balances(self):
        """
        A successful submission should not create a JournalEntry or modify the
        balance of related Accounts.
        """
        self.test_success()
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(Account.objects.all()[0].balance, 0)
        self.assertEqual(Account.objects.all()[1].balance, 0)

    def test_success_add_another_without_receipt(self):
        """
        A successful submission with the `Add More` button redirects to the
        show entry page if a receipt is not attached.
        """
        response = self.client.post(
            reverse('creditcards.views.add_creditcard_entry'),
            data={'entry-date': '2015-04-12',
                  'entry-name': 'test anarch',
                  'entry-merchant': 'test vendor',
                  'entry-amount': 20,
                  'entry-card': self.creditcard.id,
                  'transaction-TOTAL_FORMS': 5,
                  'transaction-INITIAL_FORMS': 0,
                  'transaction-MAX_NUM_FORMS': '',
                  'transaction-0-id': '',
                  'transaction-0-creditcard_entry': '',
                  'transaction-0-detail': 'test detail',
                  'transaction-0-amount': 10,
                  'transaction-0-account': self.expense_account.id,
                  'transaction-1-id': '',
                  'transaction-1-creditcard_entry': '',
                  'transaction-1-detail': 'test detail 2',
                  'transaction-1-amount': 10,
                  'transaction-1-account': self.expense_account.id,
                  'subbtn': 'Submit & Add More'})
        self.assertEqual(CreditCardEntry.objects.count(), 1)
        self.assertEqual(CreditCardTransaction.objects.count(), 2)
        self.assertRedirects(
            response, CreditCardEntry.objects.get().get_absolute_url())

    def test_success_add_another_with_receipt(self):
        """
        A successful submission with the `Add More` button redirects to the
        add entry page if a receipt is attached.
        """
        receipt = SimpleUploadedFile('test_file.txt', 'Random contents')
        response = self.client.post(
            reverse('creditcards.views.add_creditcard_entry'),
            data={'entry-date': '2015-04-12',
                  'entry-name': 'test anarch',
                  'entry-merchant': 'test vendor',
                  'entry-amount': 20,
                  'entry-card': self.creditcard.id,
                  'entry-receipts': [receipt],
                  'transaction-TOTAL_FORMS': 5,
                  'transaction-INITIAL_FORMS': 0,
                  'transaction-MAX_NUM_FORMS': '',
                  'transaction-0-id': '',
                  'transaction-0-creditcard_entry': '',
                  'transaction-0-detail': 'test detail',
                  'transaction-0-amount': 10,
                  'transaction-0-account': self.expense_account.id,
                  'transaction-1-id': '',
                  'transaction-1-creditcard_entry': '',
                  'transaction-1-detail': 'test detail 2',
                  'transaction-1-amount': 10,
                  'transaction-1-account': self.expense_account.id,
                  'subbtn': 'Submit & Add More'})
        self.assertEqual(CreditCardEntry.objects.count(), 1)
        self.assertEqual(CreditCardTransaction.objects.count(), 2)
        self.assertRedirects(
            response,
            reverse('creditcards.views.add_creditcard_entry'))

    def test_entry_fail(self):
        """
        A `POST` with invalid Entry form data will return an appropriate
        FormError & not create an Entry or Transactions.
        """
        response = self.client.post(
            reverse('creditcards.views.add_creditcard_entry'),
            data={'entry-date': '',
                  'entry-name': '',
                  'entry-merchant': '',
                  'entry-amount': 20,
                  'entry-card': self.creditcard.id,
                  'transaction-TOTAL_FORMS': 5,
                  'transaction-INITIAL_FORMS': 0,
                  'transaction-MAX_NUM_FORMS': '',
                  'transaction-0-id': '',
                  'transaction-0-creditcard_entry': '',
                  'transaction-0-detail': 'test detail',
                  'transaction-0-amount': 20,
                  'transaction-0-account': self.expense_account.id,
                  'subbtn': 'Submit'})
        self.assertEqual(response.status_code, 200)
        self.failIf(response.context['entry_form'].is_valid())
        self.assertFormError(response, 'entry_form', 'name',
                             'This field is required.')
        self.assertFormError(response, 'entry_form', 'date',
                             'This field is required.')
        self.assertFormError(response, 'entry_form', 'merchant',
                             'This field is required.')
        self.assertEqual(CreditCardEntry.objects.count(), 0)
        self.assertEqual(CreditCardTransaction.objects.count(), 0)

    def test_transaction_fail(self):
        """A `POST` with invalid Transaction data will return an error."""
        response = self.client.post(
            reverse('creditcards.views.add_creditcard_entry'),
            data={'entry-date': '2015-04-12',
                  'entry-name': 'test anarch',
                  'entry-merchant': 'test vendor',
                  'entry-amount': 20,
                  'entry-card': self.creditcard.id,
                  'transaction-TOTAL_FORMS': 5,
                  'transaction-INITIAL_FORMS': 0,
                  'transaction-MAX_NUM_FORMS': '',
                  'transaction-0-id': '',
                  'transaction-0-creditcard_entry': '',
                  'transaction-0-detail': 'test detail',
                  'transaction-0-amount': 10,
                  'transaction-0-account': self.expense_account.id,
                  'transaction-1-id': '',
                  'transaction-1-creditcard_entry': '',
                  'transaction-1-detail': 'test detail 2',
                  'transaction-1-amount': 5,
                  'transaction-1-account': '',
                  'subbtn': 'Submit'})
        self.assertEqual(response.status_code, 200)
        self.failIf(response.context['transaction_formset'].is_valid())
        form_error = response.context['transaction_formset'].forms[1].errors
        self.assertIn("This field is required", str(form_error))
        self.assertEqual(CreditCardEntry.objects.count(), 0)
        self.assertEqual(CreditCardTransaction.objects.count(), 0)

    def test_out_of_balance(self):
        """
        A `POST` with an Entry & Transaction that is out of balance should
        return an error.
        """
        response = self.client.post(
            reverse('creditcards.views.add_creditcard_entry'),
            data={'entry-date': '2015-04-12',
                  'entry-name': 'test anarch',
                  'entry-merchant': 'test vendor',
                  'entry-amount': 20,
                  'entry-card': self.creditcard.id,
                  'transaction-TOTAL_FORMS': 5,
                  'transaction-INITIAL_FORMS': 0,
                  'transaction-MAX_NUM_FORMS': '',
                  'transaction-0-id': '',
                  'transaction-0-creditcard_entry': '',
                  'transaction-0-detail': 'test detail',
                  'transaction-0-amount': 10,
                  'transaction-0-account': self.expense_account.id,
                  'transaction-1-id': '',
                  'transaction-1-creditcard_entry': '',
                  'transaction-1-detail': 'test detail 2',
                  'transaction-1-amount': 5,
                  'transaction-1-account': self.expense_account.id,
                  'subbtn': 'Submit'})
        self.assertEqual(response.status_code, 200)
        self.failIf(response.context['transaction_formset'].is_valid())
        self.assertEqual(
            response.context['transaction_formset'].non_form_errors(),
            ["The Entry Amount must equal the total Transaction Amount."])
        self.assertEqual(CreditCardEntry.objects.count(), 0)
        self.assertEqual(CreditCardTransaction.objects.count(), 0)

    def test_at_least_one_transaction(self):
        """
        A `POST` should return an error if there is not at least one
        Transaction.
        """


class ShowCreditCardEntryViewTests(TestCase):
    """Test the show_creditcard_entry view."""
    def setUp(self):
        """Create a CreditCardEntry to show."""
        self.liability_header = create_header('liability', cat_type=2)
        self.cc_account = create_account(
            "Credit Card", self.liability_header, 0)
        self.creditcard = CreditCard.objects.create(account=self.cc_account)
        self.expense_header = create_header("expenses", None, 6)
        self.expense_account = create_account(
            "expense", self.expense_header, 0, 6)
        entry_date = datetime.date.today()
        self.entry = CreditCardEntry.objects.create(
            date=entry_date, card=self.creditcard, name='test anarch',
            merchant='test merch', amount=20,
        )
        self.transaction = CreditCardTransaction.objects.create(
            creditcard_entry=self.entry, account=self.expense_account,
            amount=20,
        )

    def test_initial(self):
        """A `GET` request should return the CreditCardEntry."""
        response = self.client.get(
            reverse('creditcards.views.show_creditcard_entry',
                    kwargs={'entry_id': self.entry.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.context['journal_entry'],
                                   CreditCardEntry))
        self.assertEqual(self.entry, response.context['journal_entry'])
        self.assertItemsEqual([self.transaction],
                              response.context['transactions'])

    def test_does_not_exist(self):
        """A `GET` request to a non-existant entry should return a 404."""
        response = self.client.get(
            reverse('creditcards.views.show_creditcard_entry',
                    kwargs={'entry_id': 9001})
        )
        self.assertEqual(response.status_code, 404)


class ListCreditCardEntriesViewTests(TestCase):
    """Test the list_creditcard_entries view."""
    def setUp(self):
        """Create an initial Account, CreditCard & some CreditCardEntries."""
        create_and_login_user(self)
        self.liability_header = create_header('liability', cat_type=2)
        self.cc_account = create_account(
            "Credit Card", self.liability_header, 0)
        self.creditcard = CreditCard.objects.create(account=self.cc_account)
        self.expense_header = create_header("expenses", None, 6)
        self.expense_account = create_account(
            "expense", self.expense_header, 0, 6)
        entry_date = datetime.date(2015, 6, 11)
        self.entry = CreditCardEntry.objects.create(
            date=entry_date, card=self.creditcard, name='test anarch',
            merchant='test merch', amount=20,
        )
        self.transaction = CreditCardTransaction.objects.create(
            creditcard_entry=self.entry, account=self.expense_account,
            amount=20,
        )
        self.older_entry = CreditCardEntry.objects.create(
            date=entry_date - datetime.timedelta(days=1), card=self.creditcard,
            name='test anarch', merchant='test merch', amount=20)
        self.older_transaction = CreditCardTransaction.objects.create(
            creditcard_entry=self.older_entry, account=self.expense_account,
            amount=20)

    def test_initial(self):
        """A `GET` should display a table of all CreditCardEntries."""
        response = self.client.get(
            reverse('creditcards.views.list_creditcard_entries'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'creditcards/list.html')
        self.assertIn('entries', response.context)
        self.assertSequenceEqual([self.older_entry, self.entry],
                                 response.context['entries'])
        self.assertIn(self.entry.get_edit_url(), response.content)


class ApproveCreditCardPurchaseViewTests(TestCase):
    """Test the approval of the add_creditcard_entry view."""
    def setUp(self):
        """Create an initial Account, CreditCard & a CreditCardEntry."""
        create_and_login_user(self)
        self.liability_header = create_header('liability', cat_type=2)
        self.cc_account = create_account(
            "Credit Card", self.liability_header, 0)
        self.creditcard = CreditCard.objects.create(account=self.cc_account)
        self.expense_header = create_header("expenses", None, 6)
        self.expense_account = create_account(
            "expense", self.expense_header, 0, 6)
        entry_date = datetime.date(2015, 6, 11)
        self.entry = CreditCardEntry.objects.create(
            date=entry_date, card=self.creditcard, name='test anarch',
            merchant='test merch', amount=20,
        )
        self.transaction = CreditCardTransaction.objects.create(
            creditcard_entry=self.entry, account=self.expense_account,
            amount=20, detail='Unique Transaction Detail!',
        )

    def test_initial(self):
        """A `GET` should show a form containing the CreditCardEntry."""
        response = self.client.get(
            reverse('creditcards.views.add_creditcard_entry',
                    args=[str(self.entry.id)]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'creditcards/credit_card_form.html')
        self.assertEqual(response.context['verbose_entry_type'],
                         'Credit Card Entry')
        self.failUnless(isinstance(response.context['entry_form'],
                                   CreditCardEntryForm))
        self.failUnless(isinstance(response.context['transaction_formset'],
                                   CreditCardTransactionFormSet))

    def test_delete(self):
        """
        A `POST using the `Delete` button should delete the entry without
        creating a JournalEntry or modifying the balances of Accounts, then
        redirect to the list view.
        """
        response = self.client.post(
            reverse('creditcards.views.add_creditcard_entry',
                    args=[str(self.entry.id)]),
            data={'entry-id': self.entry.id,
                  'entry-date': '6/11/2015',
                  'entry-name': self.entry.name,
                  'entry-merchant': 'test merch',
                  'entry-amount': self.entry.amount,
                  'entry-card': self.creditcard.id,
                  'transaction-TOTAL_FORMS': 1,
                  'transaction-INITIAL_FORMS': 1,
                  'transaction-MAX_NUM_FORMS': 1,
                  'transaction-0-id': self.transaction.id,
                  'transaction-0-creditcard_entry': self.entry.id,
                  'transaction-0-detail': self.transaction.detail,
                  'transaction-0-amount': self.transaction.amount,
                  'transaction-0-account': self.expense_account.id,
                  'delete': 'Delete'})
        self.assertEqual(CreditCardEntry.objects.count(), 0)
        self.assertEqual(CreditCardTransaction.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(
            Account.objects.get(id=self.cc_account.id).balance, 0)
        self.assertEqual(
            Account.objects.get(id=self.expense_account.id).balance, 0)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertRedirects(
            response, reverse('creditcards.views.list_creditcard_entries'))

    def test_approve_success(self):
        """
        A `POST` using the `Approve` button with valid data should create a
        JournalEntry from the CreditCardEntry, then delete the CreditCardEntry.

        The detail of the Transaction crediting the CreditCard's Account should
        match the detail of the Transaction debiting the purchase's account if
        there is only one CreditCardTransaction for the CreditCardEntry.

        The page should redirect to the list of created entries.
        """
        self.assertEqual(CreditCardEntry.objects.count(), 1)
        self.assertEqual(CreditCardTransaction.objects.count(), 1)
        response = self.client.post(
            reverse('creditcards.views.add_creditcard_entry',
                    args=[str(self.entry.id)]),
            data={'entry-id': self.entry.id,
                  'entry-date': '6/11/2015',
                  'entry-name': self.entry.name,
                  'entry-merchant': 'test merch',
                  'entry-amount': self.entry.amount,
                  'entry-card': self.creditcard.id,
                  'transaction-TOTAL_FORMS': 1,
                  'transaction-INITIAL_FORMS': 1,
                  'transaction-MAX_NUM_FORMS': 1,
                  'transaction-0-id': self.transaction.id,
                  'transaction-0-creditcard_entry': self.entry.id,
                  'transaction-0-detail': self.transaction.detail,
                  'transaction-0-amount': self.transaction.amount,
                  'transaction-0-account': self.expense_account.id,
                  'subbtn': 'Approve'})
        self.assertEqual(CreditCardEntry.objects.count(), 0)
        self.assertEqual(CreditCardTransaction.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(
            Account.objects.get(id=self.cc_account.id).balance, 20)
        self.assertEqual(
            Account.objects.get(id=self.expense_account.id).balance, -20)
        transactions = Transaction.objects.all()
        self.assertEqual(transactions.count(), 2)
        self.assertEqual(transactions[0].detail, transactions[1].detail)
        self.assertRedirects(
            response, reverse('creditcards.views.list_creditcard_entries'))

    def test_approve_uses_generic_detail(self):
        """
        A valid `POST` using the `Approve` button with multiple
        CreditCardTransactions will use a generic detail for the Transaction
        crediting the CreditCard's Account.
        """
        self.entry.amount += 10
        self.entry.save()
        extra_transaction = CreditCardTransaction.objects.create(
            creditcard_entry=self.entry, account=self.expense_account,
            amount=10, detail='2nd Transaction!',
        )
        self.assertEqual(CreditCardTransaction.objects.count(), 2)

        self.client.post(
            reverse('creditcards.views.add_creditcard_entry',
                    args=[str(self.entry.id)]),
            data={'entry-id': self.entry.id,
                  'entry-date': '6/11/2015',
                  'entry-name': self.entry.name,
                  'entry-merchant': 'test merch',
                  'entry-amount': self.entry.amount,
                  'entry-card': self.creditcard.id,
                  'transaction-TOTAL_FORMS': 2,
                  'transaction-INITIAL_FORMS': 2,
                  'transaction-MAX_NUM_FORMS': 2,
                  'transaction-0-id': self.transaction.id,
                  'transaction-0-creditcard_entry': self.entry.id,
                  'transaction-0-detail': self.transaction.detail,
                  'transaction-0-amount': self.transaction.amount,
                  'transaction-0-account': self.expense_account.id,
                  'transaction-1-id': extra_transaction.id,
                  'transaction-1-creditcard_entry': self.entry.id,
                  'transaction-1-detail': extra_transaction.detail,
                  'transaction-1-amount': extra_transaction.amount,
                  'transaction-1-account': self.expense_account.id,
                  'subbtn': 'Approve'})
        self.assertEqual(CreditCardEntry.objects.count(), 0)
        self.assertEqual(CreditCardTransaction.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 1)
        transactions = Transaction.objects.all()
        self.assertEqual(transactions.count(), 3)
        self.assertEqual(transactions.get(account=self.cc_account).detail,
                         'Purchases by test anarch')

    def test_approve_modifies_entry(self):
        """
        A `POST` using the `Approve` button with valid modified data should
        update the CreditCardEntry before approving it.
        """
        self.client.post(
            reverse('creditcards.views.add_creditcard_entry',
                    args=[str(self.entry.id)]),
            data={'entry-id': self.entry.id,
                  'entry-date': '6/11/2015',
                  'entry-name': self.entry.name,
                  'entry-merchant': 'test merch',
                  'entry-amount': 35,
                  'entry-card': self.creditcard.id,
                  'transaction-TOTAL_FORMS': 1,
                  'transaction-INITIAL_FORMS': 1,
                  'transaction-MAX_NUM_FORMS': 1,
                  'transaction-0-id': self.transaction.id,
                  'transaction-0-creditcard_entry': self.entry.id,
                  'transaction-0-detail': self.transaction.detail,
                  'transaction-0-amount': 35,
                  'transaction-0-account': self.expense_account.id,
                  'subbtn': 'Approve'})
        self.assertEqual(
            Account.objects.get(id=self.cc_account.id).balance, 35)
        self.assertEqual(
            Account.objects.get(id=self.expense_account.id).balance, -35)

    def test_approve_and_next_success(self):
        """
        A `POST` using the `Approve & Open Next` button should redirect to the
        next CreditCardEntry belonging to the card by date then id.
        """
        other_cc_acount = create_account('Card 2', self.liability_header, 0)
        other_card = CreditCard.objects.create(account=other_cc_acount)
        previous_date = self.entry.date - datetime.timedelta(days=1)
        future_date = self.entry.date + datetime.timedelta(days=1)

        other_card_entry = CreditCardEntry.objects.create(
            date=self.entry.date, card=other_card, name='test anarch',
            merchant='test merch', amount=20)
        CreditCardTransaction.objects.create(
            creditcard_entry=other_card_entry, account=self.expense_account,
            amount=20)
        oldest_entry = CreditCardEntry.objects.create(
            date=previous_date - datetime.timedelta(days=1),
            card=self.creditcard, name='test anarch', merchant='test merch',
            amount=20)
        CreditCardTransaction.objects.create(
            creditcard_entry=oldest_entry, account=self.expense_account,
            amount=20)
        older_entry = CreditCardEntry.objects.create(
            date=previous_date, card=self.creditcard, name='test anarch',
            merchant='test merch', amount=20)
        CreditCardTransaction.objects.create(
            creditcard_entry=older_entry, account=self.expense_account,
            amount=20)
        future_entry = CreditCardEntry.objects.create(
            date=future_date + datetime.timedelta(days=1),
            card=self.creditcard, name='test anarch', merchant='test merch',
            amount=20)
        CreditCardTransaction.objects.create(
            creditcard_entry=future_entry, account=self.expense_account,
            amount=20)
        next_entry = CreditCardEntry.objects.create(
            date=future_date, card=self.creditcard, name='test anarch',
            merchant='test merch', amount=20)
        CreditCardTransaction.objects.create(
            creditcard_entry=next_entry, account=self.expense_account,
            amount=20)
        higher_id_entry = CreditCardEntry.objects.create(
            date=future_date, card=self.creditcard, name='test anarch',
            merchant='test merch', amount=20)
        CreditCardTransaction.objects.create(
            creditcard_entry=higher_id_entry, account=self.expense_account,
            amount=20)
        response = self.client.post(
            reverse('creditcards.views.add_creditcard_entry',
                    args=[str(self.entry.id)]),
            data={'entry-id': self.entry.id,
                  'entry-date': '6/11/2015',
                  'entry-name': self.entry.name,
                  'entry-merchant': 'test merch',
                  'entry-amount': 20,
                  'entry-card': self.creditcard.id,
                  'transaction-TOTAL_FORMS': 1,
                  'transaction-INITIAL_FORMS': 1,
                  'transaction-MAX_NUM_FORMS': 1,
                  'transaction-0-id': self.transaction.id,
                  'transaction-0-creditcard_entry': self.entry.id,
                  'transaction-0-detail': self.transaction.detail,
                  'transaction-0-amount': 20,
                  'transaction-0-account': self.expense_account.id,
                  'subbtn': 'Approve & Open Next'})
        self.assertRedirects(
            response, reverse('creditcards.views.add_creditcard_entry',
                              args=[str(next_entry.id)]))

    def test_approve_and_next_redirects_if_none(self):
        """
        A `POST` using the `Approve` button should redirect to the
        `list_creditcard_entries` view if no later CreditCardEntries exist.
        """
        response = self.client.post(
            reverse('creditcards.views.add_creditcard_entry',
                    args=[str(self.entry.id)]),
            data={'entry-id': self.entry.id,
                  'entry-date': '6/11/2015',
                  'entry-name': self.entry.name,
                  'entry-merchant': 'test merch',
                  'entry-amount': 20,
                  'entry-card': self.creditcard.id,
                  'transaction-TOTAL_FORMS': 1,
                  'transaction-INITIAL_FORMS': 1,
                  'transaction-MAX_NUM_FORMS': 1,
                  'transaction-0-id': self.transaction.id,
                  'transaction-0-creditcard_entry': self.entry.id,
                  'transaction-0-detail': self.transaction.detail,
                  'transaction-0-amount': 20,
                  'transaction-0-account': self.expense_account.id,
                  'subbtn': 'Approve & Open Next'})
        self.assertRedirects(
            response, reverse('creditcards.views.list_creditcard_entries'))

    def test_save_success(self):
        """
        A `POST` using the `Save` button with valid data should only update the
        CreditCardEntry.

        The page should redirect to the Entry's view page.
        """
        self.assertEqual(CreditCardEntry.objects.count(), 1)
        self.assertEqual(CreditCardTransaction.objects.count(), 1)
        response = self.client.post(
            reverse('creditcards.views.add_creditcard_entry',
                    args=[str(self.entry.id)]),
            data={'entry-id': self.entry.id,
                  'entry-date': '6/11/2015',
                  'entry-name': self.entry.name,
                  'entry-merchant': 'test merch',
                  'entry-amount': 42,
                  'entry-card': self.creditcard.id,
                  'transaction-TOTAL_FORMS': 1,
                  'transaction-INITIAL_FORMS': 1,
                  'transaction-MAX_NUM_FORMS': 1,
                  'transaction-0-id': self.transaction.id,
                  'transaction-0-creditcard_entry': self.entry.id,
                  'transaction-0-detail': self.transaction.detail,
                  'transaction-0-amount': 42,
                  'transaction-0-account': self.expense_account.id,
                  'subbtn': 'Submit'})
        self.assertEqual(CreditCardEntry.objects.count(), 1)
        self.assertEqual(CreditCardTransaction.objects.count(), 1)
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(
            Account.objects.get(id=self.cc_account.id).balance, 0)
        self.assertEqual(
            Account.objects.get(id=self.expense_account.id).balance, 0)
        self.assertEqual(
            CreditCardEntry.objects.get(id=self.entry.id).amount, 42)
        self.assertEqual(
            CreditCardTransaction.objects.get(id=self.transaction.id).amount,
            42)
        self.assertRedirects(response, self.entry.get_absolute_url())

    def test_save_and_next_success(self):
        """
        A `POST` using the `Save & View Next` button with valid data should
        only update the CreditCardEntry.

        The page should redirect to the approval page for the next
        CreditCardEntry belonging to the card, by creation date then id.
        """
        other_cc_acount = create_account('Card 2', self.liability_header, 0)
        other_card = CreditCard.objects.create(account=other_cc_acount)
        previous_date = self.entry.date - datetime.timedelta(days=1)
        future_date = self.entry.date + datetime.timedelta(days=1)

        other_card_entry = CreditCardEntry.objects.create(
            date=self.entry.date, card=other_card, name='test anarch',
            merchant='test merch', amount=20)
        CreditCardTransaction.objects.create(
            creditcard_entry=other_card_entry, account=self.expense_account,
            amount=20)
        oldest_entry = CreditCardEntry.objects.create(
            date=previous_date - datetime.timedelta(days=1),
            card=self.creditcard, name='test anarch', merchant='test merch',
            amount=20)
        CreditCardTransaction.objects.create(
            creditcard_entry=oldest_entry, account=self.expense_account,
            amount=20)
        older_entry = CreditCardEntry.objects.create(
            date=previous_date, card=self.creditcard, name='test anarch',
            merchant='test merch', amount=20)
        CreditCardTransaction.objects.create(
            creditcard_entry=older_entry, account=self.expense_account,
            amount=20)
        future_entry = CreditCardEntry.objects.create(
            date=future_date + datetime.timedelta(days=1),
            card=self.creditcard, name='test anarch', merchant='test merch',
            amount=20)
        CreditCardTransaction.objects.create(
            creditcard_entry=future_entry, account=self.expense_account,
            amount=20)
        next_entry = CreditCardEntry.objects.create(
            date=future_date, card=self.creditcard, name='test anarch',
            merchant='test merch', amount=20)
        CreditCardTransaction.objects.create(
            creditcard_entry=next_entry, account=self.expense_account,
            amount=20)
        higher_id_entry = CreditCardEntry.objects.create(
            date=future_date, card=self.creditcard, name='test anarch',
            merchant='test merch', amount=20)
        CreditCardTransaction.objects.create(
            creditcard_entry=higher_id_entry, account=self.expense_account,
            amount=20)

        response = self.client.post(
            reverse('creditcards.views.add_creditcard_entry',
                    args=[str(self.entry.id)]),
            data={'entry-id': self.entry.id,
                  'entry-date': '6/11/2015',
                  'entry-name': self.entry.name,
                  'entry-merchant': 'test merch',
                  'entry-amount': 42,
                  'entry-card': self.creditcard.id,
                  'transaction-TOTAL_FORMS': 1,
                  'transaction-INITIAL_FORMS': 1,
                  'transaction-MAX_NUM_FORMS': 1,
                  'transaction-0-id': self.transaction.id,
                  'transaction-0-creditcard_entry': self.entry.id,
                  'transaction-0-detail': self.transaction.detail,
                  'transaction-0-amount': 42,
                  'transaction-0-account': self.expense_account.id,
                  'subbtn': 'Submit & Open Next'})
        self.assertRedirects(
            response, reverse('creditcards.views.add_creditcard_entry',
                              args=[str(next_entry.id)]))

    def test_save_and_next_redirects_if_none(self):
        """
        A `POST` using the `Save & View Next` button with valid data should
        redirect to the `list_creditcard_entries` view if no later
        CreditCardEntries exist.
        """
        response = self.client.post(
            reverse('creditcards.views.add_creditcard_entry',
                    args=[str(self.entry.id)]),
            data={'entry-id': self.entry.id,
                  'entry-date': '6/11/2015',
                  'entry-name': self.entry.name,
                  'entry-merchant': 'test merch',
                  'entry-amount': 20,
                  'entry-card': self.creditcard.id,
                  'transaction-TOTAL_FORMS': 1,
                  'transaction-INITIAL_FORMS': 1,
                  'transaction-MAX_NUM_FORMS': 1,
                  'transaction-0-id': self.transaction.id,
                  'transaction-0-creditcard_entry': self.entry.id,
                  'transaction-0-detail': self.transaction.detail,
                  'transaction-0-amount': 20,
                  'transaction-0-account': self.expense_account.id,
                  'subbtn': 'Submit & Open Next'})
        self.assertRedirects(
            response, reverse('creditcards.views.list_creditcard_entries'))

    def test_entry_fail(self):
        """
        A `POST` with invalid entry data should not create a JournalEntry or
        Transactions.
        """
        response = self.client.post(
            reverse('creditcards.views.add_creditcard_entry',
                    args=[str(self.entry.id)]),
            data={'entry-id': self.entry.id,
                  'entry-date': '5',
                  'entry-name': self.entry.name,
                  'entry-merchant': 'test merch',
                  'entry-amount': 20,
                  'entry-card': self.creditcard.id,
                  'transaction-TOTAL_FORMS': 1,
                  'transaction-INITIAL_FORMS': 1,
                  'transaction-MAX_NUM_FORMS': 1,
                  'transaction-0-id': self.transaction.id,
                  'transaction-0-creditcard_entry': self.entry.id,
                  'transaction-0-detail': self.transaction.detail,
                  'transaction-0-amount': 20,
                  'transaction-0-account': self.expense_account.id,
                  'subbtn': 'Approve & Open Next'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CreditCardEntry.objects.count(), 1)
        self.assertEqual(CreditCardTransaction.objects.count(), 1)
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_transaction_fail(self):
        """
        A `POST` with invalid transaction data should not create a JournalEntry
        or Transactions.
        """
        response = self.client.post(
            reverse('creditcards.views.add_creditcard_entry',
                    args=[str(self.entry.id)]),
            data={'entry-id': self.entry.id,
                  'entry-date': '6/11/2015',
                  'entry-name': self.entry.name,
                  'entry-merchant': 'test merch',
                  'entry-amount': 20,
                  'entry-card': self.creditcard.id,
                  'transaction-TOTAL_FORMS': 1,
                  'transaction-INITIAL_FORMS': 1,
                  'transaction-MAX_NUM_FORMS': 1,
                  'transaction-0-id': self.transaction.id,
                  'transaction-0-creditcard_entry': self.entry.id,
                  'transaction-0-detail': self.transaction.detail,
                  'transaction-0-amount': 'jkl',
                  'transaction-0-account': self.expense_account.id,
                  'subbtn': 'Approve & Open Next'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CreditCardEntry.objects.count(), 1)
        self.assertEqual(CreditCardTransaction.objects.count(), 1)
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)
