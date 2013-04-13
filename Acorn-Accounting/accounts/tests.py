import datetime

from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.db.utils import IntegrityError
from django.template.defaultfilters import slugify
from django.test import TestCase
from django.utils.timezone import utc

from .models import Header, Account, JournalEntry, BankReceivingEntry, BankSpendingEntry, Transaction,  \
                    Event
from .forms import JournalEntryForm, TransactionFormSet, TransferFormSet, BankReceivingForm,            \
                   BankReceivingTransactionFormSet, BankSpendingForm, BankSpendingTransactionFormSet,   \
                   DateRangeForm, AccountReconcileForm, ReconcileTransactionFormSet


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
    def test_presave_signal_inherit_type(self):
        '''
        Tests that Accounts inherit their type from their root Header.
        '''
        top_head = create_header('Initial')
        child_head = Header.objects.create(name='Child', parent=top_head, slug='child')
        gchild_head = Header.objects.create(name='gChild', parent=child_head, slug='gchild')
        child_acc = Account.objects.create(name='child', parent=child_head, balance=0, slug='child')
        gchild_acc = Account.objects.create(name='gChild', parent=gchild_head, balance=0, slug='gchild')
        self.assertEqual(child_acc.type, top_head.type)
        self.assertEqual(gchild_acc.type, top_head.type)

    def test_account_get_number(self):
        '''
        Tests that Accounts are numbered according to parent number and alphabetical
        position in siblings list.
        '''
        top_head = create_header('Initial')
        child_head = Header.objects.create(name='Child', parent=top_head, slug='child')
        gchild_head = Header.objects.create(name='gChild', parent=child_head, slug='gchild')
        child_acc = Account.objects.create(name='child', parent=child_head, balance=0, slug='child')
        gchild_acc = Account.objects.create(name='gChild', parent=gchild_head, balance=0, slug='gchild')
        self.assertEqual(child_acc.get_full_number(), '{0}-{1:02d}{2:02d}'.format(child_acc.type, child_acc.parent.account_number(),
                                                                                  child_acc.account_number()))
        self.assertEqual(gchild_acc.get_full_number(), '{0}-{1:02d}{2:02d}'.format(gchild_acc.type, gchild_acc.parent.account_number(),
                                                                                  gchild_acc.account_number()))


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
        trans_newer = Transaction.objects.all()[0]
        trans_older = Transaction.objects.all()[1]
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
        create_transaction(past_entry, self.bank_account, 100)
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
        self.assertEqual(len(response.context['transaction_formset'].forms), 1)
        self.assertEqual(response.context['transaction_formset'].forms[0].instance, bank_tran)

    def test_reconcile_account_view_get_transactions_fail_old_statement_date(self):
        '''
        A `POST` to the `reconcile_account` view with a `statement_date` before
        the Accounts last_reconciled date will return an Error and no Transactions.
        '''
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
        A `POST` to the `reconcile_account` view with valid Transaction data but
        a `statement_date` before the Accounts last_reconciled date will return
        an Error and the Transactions.
        '''
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

    def test_reconcile_account_view_last_reconciled_date(self):
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
        BankReceivingEntry.objects.create(main_transaction=out_tran1, date=out_range_date2, memo='newer receive entry',
                                         payor='test payor')
        out_tran2 = Transaction.objects.create(account=self.bank_account, balance_delta=50)
        BankSpendingEntry.objects.create(main_transaction=out_tran2, date=out_range_date, memo='older spend entry',
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
        A `GET` to the `show_account_detail` view with an `account_slug`, startdate,
        and stopdate, should retrieve the Account's Transactions from that date
        period.
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

    def test_show_account_detail_view_date_fail(self):
        '''
        A `GET` to the `show_account_detail` view with an `account_slug` and invalid
        startdate or stopdate should return a DateRangeForm with errors.
        '''
        response = self.client.get(reverse('accounts.views.show_account_detail',
                                            kwargs={'account_slug': self.bank_account.slug}),
                                   data={'startdate': '10a/2/b98', 'stopdate': '11b/1threethree7/bar'})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'startdate', 'Enter a valid date.')
        self.assertFormError(response, 'form', 'stopdate', 'Enter a valid date.')


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

    def test_add_journal_entry_view_edit(self):
        '''
        A `GET` to the `add_journal_entry` view with a `journal_id` will return
        a JournalEntryForm and TransactionFormSet with the specified JournalEntry
        instance
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
        the JournalEntry, it's Transactions and whether is has been updated.
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
                                                   'journal_id': 1}))
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
