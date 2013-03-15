"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
import datetime

from django.core.urlresolvers import reverse
from django.template.defaultfilters import slugify
from django.test import TestCase
from django.test.testcases import TransactionTestCase

from .models import Header, Account, JournalEntry, BankReceivingEntry, BankSpendingEntry, Transaction
from .forms import BankReceivingForm, BankReceivingTransactionFormSet, BankSpendingForm, \
                   BankSpendingTransactionFormSet, DateRangeForm, QuickAccountForm, QuickBankForm


def create_header(name, parent=None, cat_type=2):
    return Header.objects.create(name=name, parent=parent, type=cat_type, slug=slugify(name))


def create_account(name, parent, balance, cat_type=2, bank=False):
    return Account.objects.create(name=name, slug=slugify(name), parent=parent, balance=balance,
                                  type=cat_type, bank=bank)


def create_entry(date, memo):
    return JournalEntry.objects.create(date=date, memo=memo)


def create_transaction(entry, account, delta):
    return Transaction.objects.create(journal_entry=entry, account=account,
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

    def test_quick_account_success(self):
        '''
        A `GET` to the `quick_account_search` view with an `account_id` should
        redirect to the Account's detail page
        '''
        response = self.client.get(reverse('accounts.views.quick_account_search'),
                                   data={'account': self.liability_account.id})

        self.assertRedirects(response, reverse('accounts.views.show_account_detail', args=[self.liability_account.slug]))

    def test_quick_account_fail(self):
        '''
        A `GET` to the `quick_account_search` view with an `account_id` should
        return a 404 if the Account does not exist
        '''
        response = self.client.get(reverse('accounts.views.quick_account_search'),
                                   data={'account': 9001})

        self.assertEqual(response.status_code, 404)

    def test_quick_bank_success(self):
        '''
        A `GET` to the `quick_bank_search` view with an `account_id` should
        redirect to the Account's register page
        '''
        response = self.client.get(reverse('accounts.views.quick_bank_search'),
                                   data={'bank': self.bank_account.id})

        self.assertRedirects(response, reverse('accounts.views.bank_register', args=[self.bank_account.slug]))

    def test_quick_bank_fail_not_bank(self):
        '''
        A `GET` to the `quick_bank_search` view with an `account_id` should
        return a 404 if the Account is not a bank
        '''
        response = self.client.get(reverse('accounts.views.quick_bank_search'),
                                   data={'bank': self.liability_account.id})

        self.assertEqual(response.status_code, 404)

    def test_quick_bank_fail_not_account(self):
        '''
        A `GET` to the `quick_bank_search` view with an `account_id` should
        return a 404 if the Account does not exist
        '''
        response = self.client.get(reverse('accounts.views.quick_bank_search'),
                                   data={'bank': 9001})

        self.assertEqual(response.status_code, 404)


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
                                          'transaction-0-account': self.expense_account.id
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
                                          'transaction-0-account': self.expense_account.id
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
                                          'transaction-0-account': self.expense_account.id})
        self.assertEqual(response.status_code, 200)
        self.failIf(response.context['transaction_formset'].is_valid())
        self.assertEqual(response.context['transaction_formset'].non_form_errors()[0],
                         'Transactions are out of balance.')
        self.assertEqual(BankReceivingEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_bank_receiving_add_view_edit(self):
        '''
        A `GET` to the `add_bank_entry` view with a `journal_type` of `CR` and
        a `journal_id` should display BankReceiving Forms and Formsets using an
        instance of the BankReceivingEntry with id `journal_id`.
        '''
        self.test_bank_receiving_add_view_success()
        entry = BankReceivingEntry.objects.all()[0]
        response = self.client.get(reverse('accounts.views.add_bank_entry',
                                           kwargs={'journal_type': 'CR',
                                                   'journal_id': 1}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/entry_add.html')
        self.failUnless(isinstance(response.context['entry_form'], BankReceivingForm))
        self.failUnless(isinstance(response.context['transaction_formset'], BankReceivingTransactionFormSet))
        self.assertEqual(response.context['entry_form'].instance, entry)
        self.assertEqual(response.context['entry_form'].initial['amount'],
                         -1 * entry.transaction_set.get(account__bank=True).balance_delta)
        self.assertEqual(response.context['entry_form'].initial['account'],
                         entry.transaction_set.get(account__bank=True).account)
        self.assertEqual(response.context['transaction_formset'].forms[0].instance,
                         entry.transaction_set.get(account__bank=False))
        self.assertEqual(response.context['transaction_formset'].forms[0].initial['amount'],
                         entry.transaction_set.get(account__bank=False).balance_delta)

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
                                          'entry-date': '2013-03-12',
                                          'entry-payor': 'test payor',
                                          'entry-amount': 15,
                                          'entry-memo': 'test memo',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 1,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': 2,
                                          'transaction-0-bankreceive_entry': 1,
                                          'transaction-0-detail': 'test detail',
                                          'transaction-0-amount': 15,
                                          'transaction-0-account': new_expense_account.id
                                          })
        self.assertRedirects(response, reverse('accounts.views.show_bank_entry',
                                               kwargs={'journal_type': 'CR', 'journal_id': 1}))
        self.assertEqual(BankReceivingEntry.objects.count(), 1)
        bank_account = Account.objects.get(name='bank')
        expense_account = Account.objects.get(name='expense')
        new_bank_account = Account.objects.get(name='2nd bank')
        new_expense_account = Account.objects.get(name='2nd expense')
        self.assertEqual(bank_account.balance, 0)
        self.assertEqual(expense_account.balance, 0)
        self.assertEqual(new_bank_account.balance, -15)
        self.assertEqual(new_expense_account.balance, 15)
        self.assertEqual(new_bank_account, Transaction.objects.get(id=1).account)
        self.assertEqual(new_expense_account, Transaction.objects.get(id=2).account)

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
        self.assertItemsEqual(response.context['journal_entry'].transaction_set.filter(account__bank=False), response.context['transactions'])
        self.assertEqual(response.context['journal_entry'].transaction_set.get(account__bank=True), response.context['main_transaction'])

    def test_bank_spending_add_view_initial(self):
        '''
        A `GET` to the `add_bank_entry` view with a `journal_type` of `CD`
        should display BankSpending Forms and Formsets.
        '''
        response = self.client.get(reverse('accounts.views.add_bank_entry', kwargs={'journal_type': 'CD'}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/entry_add.html')
        self.failUnless(isinstance(response.context['entry_form'], BankSpendingForm))
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
                                          'transaction-0-account': self.expense_account.id
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
                                          'entry-ach_payment': False,
                                          'entry-amount': 20,
                                          'entry-memo': 'test memo',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 0,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': '',
                                          'transaction-0-bankspend_entry': '',
                                          'transaction-0-detail': 'test detail',
                                          'transaction-0-amount': 20,
                                          'transaction-0-account': self.expense_account.id
                                          })
        self.assertEqual(response.status_code, 200)
        self.failIf(response.context['entry_form'].is_valid())
        self.assertFormError(response, 'entry_form', None, 'A check number is required if this is not an ACH payment.')
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
                                          'transaction-0-account': self.expense_account.id})
        self.assertEqual(response.status_code, 200)
        self.failIf(response.context['transaction_formset'].is_valid())
        self.assertEqual(response.context['transaction_formset'].non_form_errors()[0],
                         'Transactions are out of balance.')
        self.assertEqual(BankSpendingEntry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)

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
                                                   'journal_id': 1}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/entry_add.html')
        self.failUnless(isinstance(response.context['entry_form'], BankSpendingForm))
        self.failUnless(isinstance(response.context['transaction_formset'], BankSpendingTransactionFormSet))
        self.assertEqual(response.context['entry_form'].instance, entry)
        self.assertEqual(response.context['entry_form'].initial['amount'],
                         entry.transaction_set.get(account__bank=True).balance_delta)
        self.assertEqual(response.context['entry_form'].initial['account'],
                         entry.transaction_set.get(account__bank=True).account)
        self.assertEqual(response.context['transaction_formset'].forms[0].instance,
                         entry.transaction_set.get(account__bank=False))
        self.assertEqual(response.context['transaction_formset'].forms[0].initial['amount'],
                         -1 * entry.transaction_set.get(account__bank=False).balance_delta)

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
                                          'entry-date': '2013-03-12',
                                          'entry-ach_payment': True,
                                          'entry-payee': 'test payee',
                                          'entry-amount': 15,
                                          'entry-memo': 'test memo',
                                          'transaction-TOTAL_FORMS': 20,
                                          'transaction-INITIAL_FORMS': 1,
                                          'transaction-MAX_NUM_FORMS': '',
                                          'transaction-0-id': 2,
                                          'transaction-0-bankreceive_entry': 1,
                                          'transaction-0-detail': 'test detail',
                                          'transaction-0-amount': 15,
                                          'transaction-0-account': new_expense_account.id
                                          })
        self.assertRedirects(response, reverse('accounts.views.show_bank_entry',
                                               kwargs={'journal_type': 'CD', 'journal_id': 1}))
        self.assertEqual(BankSpendingEntry.objects.count(), 1)
        bank_account = Account.objects.get(name='bank')
        expense_account = Account.objects.get(name='expense')
        new_bank_account = Account.objects.get(name='2nd bank')
        new_expense_account = Account.objects.get(name='2nd expense')
        self.assertEqual(bank_account.balance, 0)
        self.assertEqual(expense_account.balance, 0)
        self.assertEqual(new_bank_account.balance, 15)
        self.assertEqual(new_expense_account.balance, -15)
        self.assertEqual(new_bank_account, Transaction.objects.get(id=1).account)
        self.assertEqual(new_expense_account, Transaction.objects.get(id=2).account)

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
        self.assertEqual(BankSpendingEntry.objects.get(id=1), response.context['journal_entry'])
        self.assertItemsEqual(response.context['journal_entry'].transaction_set.filter(account__bank=False), response.context['transactions'])
        self.assertEqual(response.context['journal_entry'].transaction_set.get(account__bank=True), response.context['main_transaction'])


class BankRegisterViewTests(TransactionTestCase):
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
        receive = BankReceivingEntry.objects.create(date=datetime.date.today(),
                                     memo='receive entry',
                                     payor='test payor')
        Transaction.objects.create(bankreceive_entry=receive, account=self.bank_account, balance_delta=-20, detail='bank rec')
        Transaction.objects.create(bankreceive_entry=receive, account=self.liability_account, balance_delta=20, detail='acc rec')

        spend = BankSpendingEntry.objects.create(date=datetime.date.today(), memo='spend entry',
                                  ach_payment=True, payee='test payee')
        Transaction.objects.create(bankspend_entry=spend, account=self.bank_account, balance_delta=50, detail='bank spend')
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

        receive = BankReceivingEntry.objects.create(date=in_range_date, memo='receive entry',
                                     payor='test payor')

        banktran_receive = Transaction.objects.create(bankreceive_entry=receive, account=self.bank_account, balance_delta=-20)
        Transaction.objects.create(bankreceive_entry=receive, account=self.liability_account, balance_delta=20)

        spend = BankSpendingEntry.objects.create(date=in_range_date, memo='spend entry',
                                                 ach_payment=True, payee='test payee')
        banktran_spend = Transaction.objects.create(bankspend_entry=spend, account=self.bank_account, balance_delta=50)
        Transaction.objects.create(bankspend_entry=spend, account=self.liability_account, balance_delta=-50)

        out_receive = BankReceivingEntry.objects.create(date=out_range_date2, memo='newer receive entry',
                                         payor='test payor')

        Transaction.objects.create(bankreceive_entry=out_receive, account=self.bank_account, balance_delta=-20)
        Transaction.objects.create(bankreceive_entry=out_receive, account=self.liability_account, balance_delta=20)

        out_spend = BankSpendingEntry.objects.create(date=out_range_date, memo='older spend entry',
                                                     ach_payment=True, payee='test payee')
        Transaction.objects.create(bankspend_entry=out_spend, account=self.bank_account, balance_delta=50)
        Transaction.objects.create(bankspend_entry=out_spend, account=self.liability_account, balance_delta=-50)

        response = self.client.get(reverse('accounts.views.bank_register', args=[self.bank_account.slug]),
                                   data={'startdate': date_range[0],
                                         'stopdate': date_range[1]})

        self.assertEqual(response.status_code, 200)
        self.assertItemsEqual(response.context['transactions'], [banktran_receive, banktran_spend])
        self.assertEqual(response.context['startdate'], datetime.date(2011, 1, 1))
        self.assertEqual(response.context['stopdate'], datetime.date(2012, 3, 7))
