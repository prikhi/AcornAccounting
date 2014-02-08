import datetime

from django.core.urlresolvers import reverse
from django.test import TestCase

from accounts.models import Account, HistoricalAccount
from entries.models import Transaction, BankSpendingEntry, BankReceivingEntry
from core.tests import (create_header, create_entry, create_account,
                        create_transaction, create_and_login_user)

from .fiscalyears import get_current_fiscal_year_start
from .forms import FiscalYearForm, FiscalYearAccountsFormSet
from .models import FiscalYear


class FiscalYearModuleTests(TestCase):
    """Test the utility functions in the fiscalyears.fiscalyears module."""
    def test_current_start_no_years(self):
        """
        The ``current_start`` method should return ``None`` if there are no
        ``FiscalYears``.
        """
        self.assertEqual(get_current_fiscal_year_start(), None)

    def test_current_start_one_year(self):
        """
        If there is only one ``FiscalYear`` the ``current_start`` method should
        return a date that is ``period`` amount of months before the
        ``end_month`` and ``year`` of the ``FiscalYear``.
        """
        FiscalYear.objects.create(year=2012, end_month=2, period=12)
        start = datetime.date(2011, 3, 1)
        self.assertEqual(get_current_fiscal_year_start(), start)

    def test_current_start_two_years(self):
        """
        If there are multiple  ``FiscalYears`` the ``current_start`` method
        should return a date that is one day after the ``end_month`` and
        ``year`` of the Second to Latest ``FiscalYear``.
        """
        FiscalYear.objects.create(year=2012, end_month=2, period=12)
        FiscalYear.objects.create(year=2012, end_month=6, period=12)
        start = datetime.date(2012, 3, 1)
        self.assertEqual(get_current_fiscal_year_start(), start)


class FiscalYearFormTests(TestCase):
    """
    Test the Fiscal Year creation form validation.
    """
    def setUp(self):
        """
        The FiscalYearForm requires a Current Year Earnings and Retained
        Earnings Equity Account if there are previous FiscalYears.
        """
        self.equity_header = create_header('Equity', cat_type=3)
        self.retained_account = create_account('Retained Earnings',
                                               self.equity_header, 0, 3)
        self.current_earnings = create_account('Current Year Earnings',
                                               self.equity_header, 0, 3)

    def test_first_fiscal_year_creation(self):
        """
        The first Fiscal Year created can be any month, year and period and
        does not require ``Current Year Earnings`` and ``Retained Earnings``
        Equity ``Accounts``.
        """
        Account.objects.all().delete()
        form_data = {'year': 1, 'end_month': 4, 'period': 12}
        form = FiscalYearForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_valid_next_year_same_month(self):
        """
        A valid Fiscal Year has a ``year`` greater than or equal to the current
        FiscalYear's and a ``month`` equal to the ``period``.
        """
        FiscalYear.objects.create(year=2012, end_month=2, period=12)
        form_data = {'year': 2013, 'end_month': 2, 'period': 12}
        form = FiscalYearForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_valid_next_year_same_month_13(self):
        """
        A valid Fiscal Year has a ``year`` greater than or equal to the current
        FiscalYear's and a ``month`` equal to the ``period``.
        """
        FiscalYear.objects.create(year=2012, end_month=2, period=13)
        form_data = {'year': 2013, 'end_month': 3, 'period': 13}
        form = FiscalYearForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_valid_next_year_prev_month(self):
        """
        A valid Fiscal Year has a ``year`` greater than or equal to the current
        FiscalYear's and a ``month`` less than the ``period``.
        """
        FiscalYear.objects.create(year=2012, end_month=2, period=12)
        form_data = {'year': 2013, 'end_month': 1, 'period': 12}
        form = FiscalYearForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_valid_next_year_next_month_fail(self):
        """
        A Fiscal Year is invalid if the new ``end_month`` is more than
        ``period`` months from the last ``end_month``.
        """
        FiscalYear.objects.create(year=2012, end_month=2, period=12)
        form_data = {'year': 2013, 'end_month': 3, 'period': 12}
        form = FiscalYearForm(data=form_data)
        self.assertFalse(form.is_valid())

        (form_data['end_month'], form_data['period']) = (4, 13)
        form = FiscalYearForm(data=form_data)
        self.assertFalse(form.is_valid())

    def test_valid_many_years_same_month_fail(self):
        """
        A Fiscal Year is invalid if the new ``year`` and ``end_month`` is more
        than ``period`` months from the last ``end_month``.

        Tests for bug where end_months close to previous end_month would be
        valid even if the year caused the new end date to be beyond the new
        period.
        """
        FiscalYear.objects.create(year=2012, end_month=2, period=12)
        form_data = {'year': 2014, 'end_month': 2, 'period': 12}
        form = FiscalYearForm(data=form_data)
        self.assertFalse(form.is_valid())

        (form_data['end_month'], form_data['period']) = (4, 13)
        form = FiscalYearForm(data=form_data)
        self.assertFalse(form.is_valid())

    def test_valid_same_year(self):
        """
        A valid Fiscal Year can have the same ``year`` as the current
        FiscalYear if the ``month`` is greater.
        """
        FiscalYear.objects.create(year=2012, end_month=2, period=12)
        form_data = {'year': 2012, 'end_month': 3, 'period': 12}
        form = FiscalYearForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_valid_same_year_and_month_fail(self):
        """
        A form is invalid if the ``year`` and ``month`` of the new FiscalYear
        are the same as the last's.
        """
        FiscalYear.objects.create(year=2012, end_month=2, period=12)
        form_data = {'year': 2012, 'end_month': 2, 'period': 12}
        form = FiscalYearForm(data=form_data)
        self.assertFalse(form.is_valid())

    def test_valid_same_year_prev_month_fail(self):
        """
        A form is invalid if the ``year`` of the new FiscalYear
        is the same as the last's and the ``month`` is before the last's.
        """
        FiscalYear.objects.create(year=2012, end_month=2, period=12)
        form_data = {'year': 2012, 'end_month': 1, 'period': 12}
        form = FiscalYearForm(data=form_data)
        self.assertFalse(form.is_valid())

    def test_valid_prev_year_fail(self):
        """
        Any ```FiscalYear`` with a ``year`` less than the last Year's is
        invalid.
        """
        FiscalYear.objects.create(year=2012, end_month=2, period=12)
        form_data = {'year': 2011, 'end_month': 2, 'period': 12}
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
        """
        A ``FiscalYear`` can switch from a previous ``period`` of ``13`` to
        a new ``period`` of ``12`` only if there are no ``Transactions`` in
        the previous Year's ``end_month``.
        """
        FiscalYear.objects.create(year=2012, end_month=2, period=13)
        form_data = {'year': 2013, 'end_month': 2, 'period': 12}
        form = FiscalYearForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_valid_period_change_13_to_12_fail(self):
        """
        A ``FiscalYear`` cannot switch from a previous ``period`` of ``13`` to
        a new ``period`` of ``12`` only if there are ``Transactions`` in the
        previous Year's ``end_month``.
        """
        FiscalYear.objects.create(year=2012, end_month=2, period=13)
        asset_header = create_header('asset', cat_type=1)
        asset_acc = create_account('asset', asset_header, 0, 1)
        entry = create_entry(datetime.date(2012, 2, 1), 'Entry')
        create_transaction(entry, asset_acc, -20)
        create_transaction(entry, asset_acc, 20)

        form_data = {'year': 2013, 'end_month': 2, 'period': 12}
        form = FiscalYearForm(data=form_data)
        self.assertFalse(form.is_valid())

    def test_no_earnings_accounts_fail(self):
        """
        A FiscalYear is invalid if ``Current Year Earnings`` and
        ``Retained Earnings`` Equity(type=3) ``Accounts`` do not exist and
        there are previous ``FiscalYears``.
        """
        Account.objects.all().delete()
        FiscalYear.objects.create(year=2000, end_month=4, period=12)
        form_data = {'year': 2001, 'end_month': 4, 'period': 12}
        form = FiscalYearForm(data=form_data)
        self.assertFalse(form.is_valid())


class FiscalYearAccountsFormSetTests(TestCase):
    """
    Test the FiscalYearAccountsForm initial data.
    """
    def setUp(self):
        self.asset_header = create_header('asset', cat_type=1)
        self.asset_account = create_account('asset', self.asset_header, 0, 1)

    def test_unreconciled_account_initial(self):
        """
        An Account that is unreconciled should have it's initial ``exclude``
        value unchecked.
        """
        formset = FiscalYearAccountsFormSet()
        self.assertFalse(formset.forms[0].fields['exclude'].initial)

    def test_reconciled_account_initial(self):
        """
        A reconciled Account will have its initial ``exclude`` value checked.
        """
        self.asset_account.last_reconciled = datetime.date.today()
        self.asset_account.save()
        formset = FiscalYearAccountsFormSet()
        self.assertTrue(formset.forms[0].fields['exclude'].initial)

    def test_old_reconciled_account_initial(self):
        """
        An Account reconciled a long time ago will also have it's initial
        ``exclude`` value checked.
        """
        self.asset_account.last_reconciled = (datetime.date.today() -
                                              datetime.timedelta(days=1000))
        self.asset_account.save()
        formset = FiscalYearAccountsFormSet()
        self.assertTrue(formset.forms[0].fields['exclude'].initial)


class FiscalYearViewTests(TestCase):
    """
    Test the view for creating new Fiscal Years.
    """
    def setUp(self):
        """
        Fiscal Years need Accounts to clear Transactions from.
        Equity Accounts named ``Retained Earnings`` and ``Current Year
        Earnings`` is required to move balances after purging.
        """
        create_and_login_user(self)
        self.asset_header = create_header('asset', cat_type=1)
        self.expense_header = create_header('expense', cat_type=6)
        self.bank_account = create_account('bank', self.asset_header, 0, 1,
                                           True)
        self.bank_account.last_reconciled = datetime.date(2012, 11, 1)
        self.bank_account.save()
        self.expense_account = create_account('expense', self.expense_header,
                                              0, 6)
        self.equity_header = create_header('Equity', cat_type=3)
        self.retained_account = create_account('Retained Earnings',
                                               self.equity_header, 0, 3)
        self.current_earnings = create_account('Current Year Earnings',
                                               self.equity_header, 0, 3)

    def test_add_fiscal_year_initial(self):
        """
        A `GET` to the ``add_fiscal_year`` view should display a FiscalYearForm
        and FiscalYearAccountsFormSet.
        """
        response = self.client.get(
            reverse('fiscalyears.views.add_fiscal_year'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'fiscalyears/year_add.html')
        self.assertTrue(isinstance(response.context['fiscal_year_form'],
                                   FiscalYearForm))
        self.assertTrue(isinstance(response.context['accounts_formset'],
                                   FiscalYearAccountsFormSet))
        self.assertFalse(response.context['previous_year'])

    def test_add_fiscal_year_success(self):
        """
        A ``POST`` to the ``add_fiscal_year`` view with valid data will
        create a new ``FiscalYear`` and redirect to the ``show_accounts_chart``
        view.
        """
        response = self.client.post(
            reverse('fiscalyears.views.add_fiscal_year'),
            {'year': 2013,
             'end_month': 12,
             'period': 12,
             'form-TOTAL_FORMS': 2,
             'form-INITIAL_FORMS': 2,
             'form-MAX_NUM_FORMS': 2,
             'form-0-id': self.bank_account.id, 'form-0-exclude': True,
             'form-1-id': self.expense_account.id, 'form-1-exclude': False,
             'submit': 'Start New Year'})
        self.assertRedirects(response,
                             reverse('accounts.views.show_accounts_chart'))
        self.assertEqual(FiscalYear.objects.count(), 1)

    def test_add_fiscal_year_post_fail(self):
        """
        A ``POST`` to the ``add_fiscal_year`` view with invalid data will
        return a bound ``FiscalYearForm`` with the errors.
        """
        response = self.client.post(
            reverse('fiscalyears.views.add_fiscal_year'),
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
        self.assertTemplateUsed(response, 'fiscalyears/year_add.html')
        self.assertFormError(response, 'fiscal_year_form', 'year',
                             'Enter a whole number.')
        self.assertFormError(
            response, 'fiscal_year_form', 'end_month',
            "Select a valid choice. 15 is not one of the available choices.")
        self.assertFormError(
            response, 'fiscal_year_form', 'period',
            'Select a valid choice. 11 is not one of the available choices.')

    def test_add_fiscal_year_create_historical_accounts(self):
        """
        A ``POST`` to the ``add_fiscal_year`` view with valid data and no
        previous FiscalYear will not create any HistoricalAccount entries.
        """
        self.client.post(reverse('fiscalyears.views.add_fiscal_year'),
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
        """
        A ``POST`` to the ``add_fiscal_year`` view with valid data and no
        previous ``FiscalYear`` will delete no ``JournalEntry``,
        ``BankReceivingEntry``, or ``BankSpendingEntry`` instances.
        """
        date = datetime.date(2012, 3, 20)
        entry = create_entry(date, 'reconciled entry')
        bank_trans = create_transaction(entry, self.bank_account, 20)
        bank_trans.reconciled = True
        bank_trans.save()
        create_transaction(entry, self.expense_account, 20)
        unreconciled_entry = create_entry(date, 'unreconciled entry')
        create_transaction(unreconciled_entry, self.bank_account, 35)
        create_transaction(unreconciled_entry, self.expense_account, 20)
        self.client.post(reverse('fiscalyears.views.add_fiscal_year'),
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
        """
        A ``POST`` to the ``add_fiscal_year`` view with valid data and no
        previous ``FiscalYear`` will not change ``Account`` balances.
        """
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
        self.client.post(reverse('fiscalyears.views.add_fiscal_year'),
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
        self.current_earnings = Account.objects.get(
            id=self.current_earnings.id)
        self.retained_account = Account.objects.get(
            id=self.retained_account.id)
        self.assertEqual(self.bank_account.balance, 55)
        self.assertEqual(self.expense_account.balance, 20)
        self.assertEqual(self.current_earnings.balance, 20)
        self.assertEqual(self.retained_account.balance, 0)

    def test_add_fiscal_year_with_previous_initial(self):
        """
        If there is a previous FiscalYear, a ``GET`` to the ``add_fiscal_year``
        view should display a FiscalYearForm, FiscalYearAccountsFormSet and the
        previous FiscalYear.
        """
        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        prev = FiscalYear.objects.create(year=2012, end_month=12, period=12)
        response = self.client.get(
            reverse('fiscalyears.views.add_fiscal_year'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'fiscalyears/year_add.html')
        self.assertTrue(isinstance(response.context['fiscal_year_form'],
                                   FiscalYearForm))
        self.assertTrue(isinstance(response.context['accounts_formset'],
                                   FiscalYearAccountsFormSet))
        self.assertEqual(response.context['previous_year'], prev)

    def test_add_fiscal_year_with_previous_success(self):
        """
        A ``POST`` to the ``add_fiscal_year`` view with valid data and a
        previous FiscalYear will redirect to the ``show_accounts_chart`` view.
        """
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        response = self.client.post(
            reverse('fiscalyears.views.add_fiscal_year'),
            {'year': 2013,
             'end_month': 12,
             'period': 12,
             'form-TOTAL_FORMS': 2,
             'form-INITIAL_FORMS': 2,
             'form-MAX_NUM_FORMS': 2,
             'form-0-id': self.bank_account.id, 'form-0-exclude': True,
             'form-1-id': self.expense_account.id, 'form-1-exclude': False,
             'submit': 'Start New Year'})
        self.assertRedirects(response,
                             reverse('accounts.views.show_accounts_chart'))
        self.assertEqual(FiscalYear.objects.count(), 2)

    def test_add_fiscal_year_with_previous_create_historical_accounts(self):
        """
        A ``POST`` to the ``add_fiscal_year`` view with valid data and one
        previous FiscalYear will create HistoricalAccounts from the previous
        Years end date to ``period`` months before.
        """
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        self.client.post(reverse('fiscalyears.views.add_fiscal_year'),
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
        """
        A ``POST`` to the ``add_fiscal_year`` view with valid data and one
        previous ``FiscalYear`` will delete all ``JournalEntry``,
        ``BankReceivingEntry``, and ``BankSpendingEntry`` from the previous
        ``FiscalYear`` excluding those with unreconciled ``Transactions``
        for ``Accounts`` in the POSTed data.
        """
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
        unreconciled_bank = create_transaction(unreconciled_entry,
                                               self.bank_account, 35)
        unreconciled_expense = create_transaction(unreconciled_entry,
                                                  self.expense_account, 20)
        self.client.post(reverse('fiscalyears.views.add_fiscal_year'),
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
        # Includes 2 Transactions for Current Year -> Retained entry
        self.assertEqual(Transaction.objects.count(), 4)
        curr_trans = Account.objects.get(
            id=self.current_earnings.id).transaction_set.all()[0]
        ret_trans = Account.objects.get(
            id=self.retained_account.id).transaction_set.all()[0]
        self.assertSequenceEqual(
            Transaction.objects.all(),
            [unreconciled_bank, unreconciled_expense, curr_trans, ret_trans])

    def test_add_fiscal_year_with_previous_purge_bank_spending_entries(self):
        """
        A ``POST`` to the ``add_fiscal_year`` view with valid data and one
        previous ``FiscalYear`` will delete all ``JournalEntry``,
        ``BankReceivingEntry``, and ``BankSpendingEntry`` from the previous
        ``FiscalYear`` excluding those with unreconciled ``Transactions``
        for ``Accounts`` in the POSTed data.
        """
        bank_account2 = create_account('bank2', self.asset_header, 0, 1, True)
        bank_account2.last_reconciled = datetime.date(2012, 11, 1)
        bank_account2.save()
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        date = datetime.date(2012, 3, 20)
        # This Account is excluded but the entry is reconciled.
        entry_main = Transaction.objects.create(
            account=self.bank_account, balance_delta=20, reconciled=True)
        entry = BankSpendingEntry.objects.create(
            main_transaction=entry_main, date=date, memo='reconciled entry',
            payee='test payee', ach_payment=True)
        Transaction.objects.create(
            account=self.expense_account, balance_delta=-20,
            bankspend_entry=entry)
        # This Account is not excluded so the entry will be deleted
        purged_entry_main = Transaction.objects.create(
            account=bank_account2, balance_delta=20, reconciled=False)
        purged_entry = BankSpendingEntry.objects.create(
            main_transaction=purged_entry_main, date=date,
            memo='unreconiled but not excluded', payee='test payee',
            ach_payment=True)
        Transaction.objects.create(
            account=self.expense_account, balance_delta=-20,
            bankspend_entry=purged_entry)
        # This Account is excluded and the entry is unreconciled so it
        # will stay
        unreconciled_bank = Transaction.objects.create(
            account=self.bank_account, balance_delta=20, reconciled=False)
        unreconciled_entry = BankSpendingEntry.objects.create(
            main_transaction=unreconciled_bank, date=date,
            memo='unreconciled entry', payee='test payee', ach_payment=True)
        unreconciled_expense = Transaction.objects.create(
            account=self.expense_account, balance_delta=-20,
            bankspend_entry=unreconciled_entry)
        self.client.post(
            reverse('fiscalyears.views.add_fiscal_year'),
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
        # Includes 2 Transactions for Current Year -> Retained entry
        self.assertEqual(Transaction.objects.count(), 4)
        curr_trans = Account.objects.get(
            id=self.current_earnings.id).transaction_set.all()[0]
        ret_trans = Account.objects.get(
            id=self.retained_account.id).transaction_set.all()[0]
        self.assertSequenceEqual(
            Transaction.objects.all(),
            [unreconciled_bank, unreconciled_expense, curr_trans, ret_trans])

    def test_add_fiscal_year_with_previous_purge_bank_receiving_entries(self):
        """
        A ``POST`` to the ``add_fiscal_year`` view with valid data and one
        previous ``FiscalYear`` will delete all ``JournalEntry``,
        ``BankReceivingEntry``, and ``BankSpendingEntry`` from the previous
        ``FiscalYear`` excluding those with unreconciled ``Transactions``
        for ``Accounts`` in the POSTed data.
        """
        bank_account2 = create_account('bank2', self.asset_header, 0, 1, True)
        bank_account2.last_reconciled = datetime.date(2012, 11, 1)
        bank_account2.save()
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        date = datetime.date(2012, 3, 20)
        # This Account is excluded but the entry is reconciled.
        entry_main = Transaction.objects.create(
            account=self.bank_account, balance_delta=-20, reconciled=True)
        entry = BankReceivingEntry.objects.create(
            main_transaction=entry_main, date=date, memo='reconciled entry',
            payor='test payor')
        Transaction.objects.create(
            account=self.expense_account, balance_delta=20,
            bankreceive_entry=entry)
        # This Account is not excluded so the entry will be deleted
        purged_entry_main = Transaction.objects.create(
            account=bank_account2, balance_delta=-20, reconciled=False)
        purged_entry = BankReceivingEntry.objects.create(
            main_transaction=purged_entry_main, date=date,
            memo='unreconiled but not excluded', payor='test payor')
        Transaction.objects.create(
            account=self.expense_account, balance_delta=20,
            bankreceive_entry=purged_entry)
        # This Account is excluded and the entry is unreconciled so it
        # will stay
        unreconciled_bank = Transaction.objects.create(
            account=self.bank_account, balance_delta=-20, reconciled=False)
        unreconciled_entry = BankReceivingEntry.objects.create(
            main_transaction=unreconciled_bank, date=date,
            memo='unreconciled entry', payor='test payor')
        unreconciled_expense = Transaction.objects.create(
            account=self.expense_account, balance_delta=20,
            bankreceive_entry=unreconciled_entry)
        self.client.post(
            reverse('fiscalyears.views.add_fiscal_year'),
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
        # Includes 2 Transactions for Current Year -> Retained entry
        self.assertEqual(Transaction.objects.count(), 4)
        curr_trans = Account.objects.get(
            id=self.current_earnings.id).transaction_set.all()[0]
        ret_trans = Account.objects.get(
            id=self.retained_account.id).transaction_set.all()[0]
        self.assertSequenceEqual(
            Transaction.objects.all(),
            [unreconciled_bank, unreconciled_expense, curr_trans, ret_trans])

    def test_add_fiscal_year_with_previous_balance_changes(self):
        """
        A ``POST`` to the ``add_fiscal_year`` view with valid data and a
        previous ``FiscalYear`` will set new ``Account`` balances.
        Accounts with types 1-3 will have their balance set to the last

        HistoricalAccount of the just completed FiscalYear, plus any
        Transactions in the new FiscalYear.

        Accounts with type 4-8 will have their balance set to the sum of its
        Transactions balance_deltas in the new FiscalYear.

        The balance of the ``Current Year Earnings`` account will be moved
        to the ``Retained Earnings`` account.
        """
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        other_expense_account = create_account('Other Expense',
                                               self.expense_header, 0, 6)
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
        self.client.post(reverse('fiscalyears.views.add_fiscal_year'),
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
        other_expense_account = Account.objects.get(
            id=other_expense_account.id)
        self.current_earnings = Account.objects.get(
            id=self.current_earnings.id)
        self.retained_account = Account.objects.get(
            id=self.retained_account.id)
        self.assertEqual(self.bank_account.balance, 55)
        self.assertEqual(self.expense_account.balance, 0)
        self.assertEqual(other_expense_account.balance, 2)
        self.assertEqual(self.current_earnings.balance, 0)
        self.assertEqual(self.retained_account.balance, 20)

    def test_add_fiscal_year_w_two_previous_create_historical_accounts(self):
        """
        A ``POST`` to the ``add_fiscal_year`` view with valid data and two
        previous FiscalYear will create HistoricalAccount entries for the
        time period of the previous FiscalYear.

        HistoricalAccounts with a ``type`` between 1 and 3 will have balance
        sums per month while those with a ``type`` between 4 and 8 will have
        the net_change for the month.
        """
        jan = datetime.date(2012, 1, 20)
        jan_entry = create_entry(jan, 'jan entry')
        create_transaction(jan_entry, self.bank_account, -20)
        create_transaction(jan_entry, self.expense_account, -15)

        sept = datetime.date(2012, 9, 4)
        sept_entry = create_entry(sept, 'sept entry')
        create_transaction(sept_entry, self.bank_account, -20)
        create_transaction(sept_entry, self.expense_account, -15)

        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        FiscalYear.objects.create(year=2012, end_month=12, period=12)

        self.client.post(reverse('fiscalyears.views.add_fiscal_year'),
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

        jan_bank = HistoricalAccount.objects.get(
            date__month=1, date__year=2012, name=self.bank_account.name)
        jan_exp = HistoricalAccount.objects.get(
            date__month=1, date__year=2012, name=self.expense_account.name)
        jan_earn = HistoricalAccount.objects.get(
            date__month=1, date__year=2012, name=self.current_earnings.name)
        self.assertEqual(jan_bank.amount, -20)
        self.assertEqual(jan_exp.amount, -15)
        self.assertEqual(jan_earn.amount, -15)

        mar_bank = HistoricalAccount.objects.get(
            date__month=3, date__year=2012, name=self.bank_account.name)
        mar_exp = HistoricalAccount.objects.get(
            date__month=3, date__year=2012, name=self.expense_account.name)
        mar_earn = HistoricalAccount.objects.get(
            date__month=3, date__year=2012, name=self.current_earnings.name)
        self.assertEqual(mar_bank.amount, -20)
        self.assertEqual(mar_exp.amount, 0)
        self.assertEqual(mar_earn.amount, -15)

        sept_bank = HistoricalAccount.objects.get(
            date__month=9, date__year=2012, name=self.bank_account.name)
        sept_exp = HistoricalAccount.objects.get(
            date__month=9, date__year=2012, name=self.expense_account.name)
        sept_earn = HistoricalAccount.objects.get(
            date__month=9, date__year=2012, name=self.current_earnings.name)
        self.assertEqual(sept_bank.amount, -40)
        self.assertEqual(sept_exp.amount, -15)
        self.assertEqual(sept_earn.amount, -30)

    def test_add_fiscal_year_w_two_previous_purge_entries(self):
        """
        A ``POST`` to the ``add_fiscal_year`` view with valid data and two
        previous ``FiscalYears`` will purge all ``JournalEntry``,
        ``BankReceivingEntry`` and ``BankReceivingEntry`` instances in the last
        ``FiscalYear`` excluding Entries containing unreconciled
        ``Transactions`` for ``Accounts`` in the POSTed data.
        """
        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        date = datetime.date(2012, 3, 20)
        entry = create_entry(date, 'reconciled entry')
        bank_trans = create_transaction(entry, self.bank_account, 20)
        bank_trans.reconciled = True
        bank_trans.save()
        create_transaction(entry, self.expense_account, 20)
        unreconciled_entry = create_entry(date, 'unreconciled entry')
        unreconciled_bank = create_transaction(unreconciled_entry,
                                               self.bank_account, 35)
        unreconciled_expense = create_transaction(unreconciled_entry,
                                                  self.expense_account, 20)
        self.client.post(reverse('fiscalyears.views.add_fiscal_year'),
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
        # Includes 2 Transactions for Current Year -> Retained entry
        self.assertEqual(Transaction.objects.count(), 4)
        curr_trans = Account.objects.get(
            id=self.current_earnings.id).transaction_set.all()[0]
        ret_trans = Account.objects.get(
            id=self.retained_account.id).transaction_set.all()[0]
        self.assertSequenceEqual(
            Transaction.objects.all(),
            [unreconciled_bank, unreconciled_expense, curr_trans, ret_trans])

    def test_add_fiscal_year_w_two_previous_purge_bank_spending_entries(self):
        """
        A ``POST`` to the ``add_fiscal_year`` view with valid data and two
        previous ``FiscalYears`` will purge all ``JournalEntry``,
        ``BankReceivingEntry`` and ``BankReceivingEntry`` instances in the last
        ``FiscalYear`` excluding Entries containing unreconciled
        ``Transactions`` for ``Accounts`` in the POSTed data.
        """
        bank_account2 = create_account('bank2', self.asset_header, 0, 1, True)
        bank_account2.last_reconciled = datetime.date(2012, 11, 1)
        bank_account2.save()
        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        date = datetime.date(2012, 3, 20)
        # This Account is excluded but the entry is reconciled.
        entry_main = Transaction.objects.create(
            account=self.bank_account, balance_delta=20, reconciled=True)
        entry = BankSpendingEntry.objects.create(
            main_transaction=entry_main, date=date, memo='reconciled entry',
            payee='test payee', ach_payment=True)
        Transaction.objects.create(
            account=self.expense_account, balance_delta=-20,
            bankspend_entry=entry)
        # This Account is not excluded so the entry will be deleted
        purged_entry_main = Transaction.objects.create(
            account=bank_account2, balance_delta=20, reconciled=False)
        purged_entry = BankSpendingEntry.objects.create(
            main_transaction=purged_entry_main, date=date,
            memo='unreconiled but not excluded', payee='test payee',
            ach_payment=True)
        Transaction.objects.create(
            account=self.expense_account, balance_delta=-20,
            bankspend_entry=purged_entry)
        # This Account is excluded and the entry is unreconciled so
        # it will stay
        unreconciled_bank = Transaction.objects.create(
            account=self.bank_account, balance_delta=20, reconciled=False)
        unreconciled_entry = BankSpendingEntry.objects.create(
            main_transaction=unreconciled_bank, date=date,
            memo='unreconciled entry', payee='test payee', ach_payment=True)
        unreconciled_expense = Transaction.objects.create(
            account=self.expense_account, balance_delta=-20,
            bankspend_entry=unreconciled_entry)
        self.client.post(
            reverse('fiscalyears.views.add_fiscal_year'),
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
        # Includes 2 Transactions for Current Year -> Retained entry
        self.assertEqual(Transaction.objects.count(), 4)
        curr_trans = Account.objects.get(
            id=self.current_earnings.id).transaction_set.all()[0]
        ret_trans = Account.objects.get(
            id=self.retained_account.id).transaction_set.all()[0]
        self.assertSequenceEqual(
            Transaction.objects.all(),
            [unreconciled_bank, unreconciled_expense, curr_trans, ret_trans])

    def test_add_fiscal_year_w_two_previous_purge_bank_receiving_entries(self):
        """
        A ``POST`` to the ``add_fiscal_year`` view with valid data and two
        previous ``FiscalYears`` will purge all ``JournalEntry``,
        ``BankReceivingEntry`` and ``BankReceivingEntry`` instances in the last
        ``FiscalYear`` excluding Entries containing unreconciled
        ``Transactions`` for ``Accounts`` in the POSTed data.
        """
        bank_account2 = create_account('bank2', self.asset_header, 0, 1, True)
        bank_account2.last_reconciled = datetime.date(2012, 11, 1)
        bank_account2.save()
        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        date = datetime.date(2012, 3, 20)
        # This Account is excluded but the entry is reconciled.
        entry_main = Transaction.objects.create(
            account=self.bank_account, balance_delta=-20, reconciled=True)
        entry = BankReceivingEntry.objects.create(
            main_transaction=entry_main, date=date, memo='reconciled entry',
            payor='test payor')
        Transaction.objects.create(
            account=self.expense_account, balance_delta=20,
            bankreceive_entry=entry)
        # This Account is not excluded so the entry will be deleted
        purged_entry_main = Transaction.objects.create(
            account=bank_account2, balance_delta=-20, reconciled=False)
        purged_entry = BankReceivingEntry.objects.create(
            main_transaction=purged_entry_main, date=date,
            memo='unreconiled but not excluded', payor='test payor')
        Transaction.objects.create(
            account=self.expense_account, balance_delta=20,
            bankreceive_entry=purged_entry)
        # This Account is excluded and the entry is unreconciled so it will
        # stay
        unreconciled_bank = Transaction.objects.create(
            account=self.bank_account, balance_delta=-20, reconciled=False)
        unreconciled_entry = BankReceivingEntry.objects.create(
            main_transaction=unreconciled_bank, date=date,
            memo='unreconciled entry', payor='test payor')
        unreconciled_expense = Transaction.objects.create(
            account=self.expense_account, balance_delta=20,
            bankreceive_entry=unreconciled_entry)
        self.client.post(
            reverse('fiscalyears.views.add_fiscal_year'),
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
        # Includes 2 Transactions for Current Year -> Retained entry
        self.assertEqual(Transaction.objects.count(), 4)
        curr_trans = Account.objects.get(
            id=self.current_earnings.id).transaction_set.all()[0]
        ret_trans = Account.objects.get(
            id=self.retained_account.id).transaction_set.all()[0]
        self.assertSequenceEqual(
            Transaction.objects.all(),
            [unreconciled_bank, unreconciled_expense, curr_trans, ret_trans])

    def test_add_fiscal_year_with_previous_purge_entries_main_trans(self):
        """
        A ``POST`` to the ``add_fiscal_year`` view with valid data and two
        previous ``FiscalYears`` will purge the `main_transactions` of
        ``BankReceivingEntry`` and ``BankReceivingEntry`` instances in the last
        ``FiscalYear`` excluding Entries containing unreconciled
        ``Transactions`` for ``Accounts`` in the POSTed data.

        Tests for regression in bug where `main_transaction` was not being
        deleted in FiscalYear creation.
        """
        FiscalYear.objects.create(year=2011, end_month=12, period=12)
        FiscalYear.objects.create(year=2012, end_month=12, period=12)
        date = datetime.date(2012, 3, 20)
        unreconciled_main = Transaction.objects.create(
            date=date, detail='unrec main', account=self.bank_account,
            balance_delta=50)
        unreconciled_bank_entry = BankSpendingEntry.objects.create(
            ach_payment=True, main_transaction=unreconciled_main, date=date,
            memo='unreconciled')
        Transaction.objects.create(
            bankspend_entry=unreconciled_bank_entry, balance_delta=-50,
            account=self.expense_account)
        reconciled_main = Transaction.objects.create(
            date=date, detail='rec main', account=self.bank_account,
            balance_delta=50, reconciled=True)
        reconciled_bank_entry = BankReceivingEntry.objects.create(
            payor='test', main_transaction=reconciled_main, date=date,
            memo='reconciled')
        Transaction.objects.create(
            bankreceive_entry=reconciled_bank_entry, detail='rec gen',
            balance_delta=-50, account=self.expense_account)
        self.client.post(
            reverse('fiscalyears.views.add_fiscal_year'),
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
        self.assertTrue(
            Transaction.objects.filter(detail='unrec main').exists())
        self.assertFalse(
            Transaction.objects.filter(detail='rec main').exists())
        self.assertFalse(
            Transaction.objects.filter(detail='rec gen').exists())
        self.assertEqual(BankReceivingEntry.objects.count(), 0)
        self.assertEqual(BankSpendingEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 4)
