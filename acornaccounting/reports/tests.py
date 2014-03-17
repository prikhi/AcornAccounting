import datetime

from django.core.urlresolvers import reverse
from django.test import TestCase

from core.forms import DateRangeForm
from core.tests import (create_header, create_account, create_entry,
                        create_transaction)
from entries.models import Transaction
from events.models import Event

from .views import (_get_account_details, _get_profit_totals,
                    _get_profit_loss_header_totals)


class EventsReportViewTests(TestCase):
    """Test the events_report view."""
    def setUp(self):
        """Create some events and transactions."""
        liability_header = create_header('Liability Account')
        liability_account = create_account('Liability Account',
                                           liability_header, 0)
        self.event1 = Event.objects.create(name="test", number=1201,
                                           date=datetime.date.today(),
                                           city="Baltimore", state="MD")
        self.event2 = Event.objects.create(name="test", number=1202,
                                           date=datetime.date.today(),
                                           city="Richmond", state="VA")
        entry = create_entry(datetime.date.today(), 'test memo')
        Transaction.objects.create(journal_entry=entry,
                                   account=liability_account,
                                   balance_delta=25, event=self.event1)
        Transaction.objects.create(journal_entry=entry,
                                   account=liability_account,
                                   balance_delta=-15, event=self.event2)

    def test_initial(self):
        """
        A `GET` to the `events_report` view will retrieve all Events, ordered
        by date.
        """
        response = self.client.get(reverse('reports.views.events_report'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'reports/events.html')
        self.assertSequenceEqual(response.context['events'],
                                 [self.event1, self.event2])

    def test_no_events(self):
        """
        A `GET` to the `events_report` view will show an appropriate message if
        no Events exist.
        """
        self.event1.delete()
        self.event2.delete()

        response = self.client.get(reverse('reports.views.events_report'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'reports/events.html')
        self.assertSequenceEqual(response.context['events'],
                                 [])
        self.assertIn("no Events were found", response.content)


class ProfitLossReportViewTests(TestCase):
    """Test the profit_loss_report view."""
    def setUp(self):
        """
        The report requires Income, Cost of Sales, Expense, Other Income and
        Other Expense Headers and Accounts.
        """
        self.income_header = create_header('Income Header', cat_type=4)
        self.income_account = create_account('Income Account',
                                             self.income_header, 0, 4)
        self.cos_header = create_header('Cost of Sales Header', cat_type=5)
        self.cos_account = create_account('Cost of Sales Account',
                                          self.cos_header, 0, 5)
        self.expense_header = create_header('Expense Header', cat_type=6)
        self.expense_account = create_account('Expense Account',
                                              self.expense_header, 0, 6)
        self.oincome_header = create_header('Other Income Header', cat_type=7)
        self.oincome_account = create_account('Other Income Account',
                                              self.oincome_header, 0, 7)
        self.oexpense_header = create_header('Other Expense Header',
                                             cat_type=8)
        self.oexpense_account = create_account('Other Expense Account',
                                               self.oexpense_header, 0, 8)

    def test_initial(self):
        """
        A `GET` to the `profit_loss_report` view should return a DateRangeForm,
        start/stop dates and multiple root Headers and counter context
        variables.

        The start date should be the beginning of the current year and the stop
        date should be the current date.

        The view should pass in variables reflecting Header root nodes:
            `income`, `cost_of_goods_sold`, `expenses`, `other_incomes`,
            `other_expenses`

        and variables of the counters:
            `gross_profit`, `operating_profit`, `net_profit_or_loss`
        """
        today = datetime.date.today()
        first_of_year = datetime.date(today.year, 1, 1)

        response = self.client.get(
            reverse('reports.views.profit_loss_report'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'reports/profit_loss.html')
        self.assertEqual(response.context['start_date'], first_of_year)
        self.assertEqual(response.context['stop_date'], today)
        self.assertIn('gross_profit', response.context)
        self.assertIn('operating_profit', response.context)
        self.assertIn('net_profit', response.context)
        self.assertIn('headers', response.context)
        self.assertIn('income', response.context['headers'])
        self.assertIn('cost_of_goods_sold', response.context['headers'])
        self.assertIn('expenses', response.context['headers'])
        self.assertIn('other_income', response.context['headers'])
        self.assertIn('other_expenses', response.context['headers'])

    def test_date_range(self):
        """A valid `GET` request will only use Transactions in the range."""
        start_date = datetime.date(2014, 2, 3)
        stop_date = datetime.date(2014, 5, 3)

        before_range = datetime.date(2014, 1, 12)
        in_range = datetime.date(2014, 3, 25)
        after_range = datetime.date(2014, 9, 22)

        past_entry = create_entry(before_range, "Before the report range")
        create_transaction(past_entry, self.income_account, -50)
        create_transaction(past_entry, self.expense_account, 50)

        in_range_entry = create_entry(in_range, "In the report range")
        create_transaction(in_range_entry, self.income_account, 23)
        create_transaction(in_range_entry, self.expense_account, -23)

        future_entry = create_entry(after_range, "After the report range")
        create_transaction(future_entry, self.income_account, 100)
        create_transaction(future_entry, self.expense_account, -100)

        response = self.client.get(reverse('reports.views.profit_loss_report'),
                                   data={'start_date': start_date,
                                         'stop_date': stop_date})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['headers']['income'].total, 23)
        self.assertEqual(response.context['headers']['expenses'].total, 23)

    def test_date_range_fail(self):
        """A `GET` with invalid DateRangeForm data should show errors."""
        response = self.client.get(
            reverse('reports.views.profit_loss_report'),
            data={'start_date': '10a/2/b98',
                  'stop_date': '11b/1threethree7/bar'})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'start_date',
                             'Enter a valid date.')
        self.assertFormError(response, 'form', 'stop_date',
                             'Enter a valid date.')

    def test_get_profit_loss_header_totals(self):
        """
        The function should return a root Header with the descendants and
        total attributes.
        """
        child_header = create_header("Child Income", self.income_header, 4)
        gchild_account = create_account("GrandChild Income", child_header,
                                        0, 4)
        gchild_header = create_header("Grandchild Income", child_header, 4)
        ggchild_account = create_account("Great Grandchild Income",
                                         gchild_header, 0, 4)

        entry = create_entry(datetime.date.today(), "test entry")
        create_transaction(entry, self.income_account, 25)
        create_transaction(entry, gchild_account, 47)
        create_transaction(entry, ggchild_account, 82)

        start_date = datetime.date(1, 1, 1)
        stop_date = datetime.date.today()

        root_header = _get_profit_loss_header_totals(4, start_date, stop_date)
        child_header_result = root_header.descendants[0]
        gchild_header_result = child_header_result.descendants[0]

        self.assertEqual(root_header.total, 154)
        self.assertSequenceEqual(root_header.descendants, [child_header])
        self.assertEqual(child_header_result.total, 129)
        self.assertSequenceEqual(child_header_result.descendants,
                                 [gchild_header])
        self.assertEqual(gchild_header_result.total, 82)

    def test_get_profit_loss_header_totals_flipped(self):
        """
        The totals for Expenses, Cost of Goods Sold and Other Expenses should
        display the value total, not the credit/debit total.
        """
        child_header = create_header("Child Expense", self.expense_header, 6)
        gchild_account = create_account("GrandChild Expense", child_header,
                                        0, 6)
        gchild_header = create_header("Grandchild Expense", child_header, 6)
        ggchild_account = create_account("Great Grandchild Expense",
                                         gchild_header, 0, 6)

        entry = create_entry(datetime.date.today(), "test entry")
        create_transaction(entry, self.expense_account, 25)
        create_transaction(entry, gchild_account, 47)
        create_transaction(entry, ggchild_account, 82)

        start_date = datetime.date(1, 1, 1)
        stop_date = datetime.date.today()

        root_header = _get_profit_loss_header_totals(6, start_date, stop_date)
        child_header_result = root_header.descendants[0]
        gchild_header_result = child_header_result.descendants[0]

        self.assertEqual(root_header.total, -154)
        self.assertSequenceEqual(root_header.descendants, [child_header])
        self.assertEqual(child_header_result.total, -129)
        self.assertSequenceEqual(child_header_result.descendants,
                                 [gchild_header])
        self.assertEqual(gchild_header_result.total, -82)

    def test_get_profit_loss_header_totals_max_child_depth(self):
        """
        The function should only nest up to the grandchildren of the root
        header.
        """
        child_header = create_header("Child Income", self.income_header, 4)
        gchild_header = create_header("Grandchild Income", child_header, 4)
        create_header("Great Grandchild Income", gchild_header, 4)
        start_date = datetime.date(1, 1, 1)
        stop_date = datetime.date.today()

        root_header = _get_profit_loss_header_totals(4, start_date, stop_date)
        max_depth_header = root_header.descendants[0].descendants[0]

        self.assertFalse(hasattr(max_depth_header, 'descendants'))

    def test_get_profit_totals(self):
        """The function should correctly calculate all profit counters.

        GP = Income - Cost of Sales
        OP = GP - Expenses
        NP = OP + Other Income - Other Expenses
        """
        class MockHeader(object):
            def __init__(self, total):
                self.total = total

        headers = {'income': MockHeader(500),
                   'cost_of_goods_sold': MockHeader(125),
                   'expenses': MockHeader(75),
                   'other_income': MockHeader(25),
                   'other_expenses': MockHeader(50)}

        gross_profit, operating_profit, net_profit = _get_profit_totals(
            headers)

        self.assertEqual(gross_profit, 375)
        self.assertEqual(operating_profit, 300)
        self.assertEqual(net_profit, 275)


class TrialBalanceReportViewTests(TestCase):
    """Test the trial_balance_report view."""
    def setUp(self):
        """Create an Asset and Liability account."""
        asset_header = create_header('Asset Header', cat_type=1)
        self.asset_account = create_account('Asset Account', asset_header, 0)
        liability_header = create_header('Liability Header')
        self.liability_account = create_account('Liability Account',
                                                liability_header, 0)

    def test_initial(self):
        """
        A `GET` to the `trial_balance_report` view should return a
        DateRangeForm, start/stop dates and a list of Account dictionaries,
        each dictionary should contain a number, name, beginning balance, total
        debit, total credit, net change and ending balance.

        The start date should be the beginning of the current year and the stop
        date should be the current date.
        """
        today = datetime.date.today()
        first_of_year = datetime.date(today.year, 1, 1)

        past_entry = create_entry(first_of_year - datetime.timedelta(days=1),
                                  "Before the default report range")
        create_transaction(past_entry, self.asset_account, -25)
        create_transaction(past_entry, self.liability_account, 25)

        in_range_entry = create_entry(today, "In the default report range")
        create_transaction(in_range_entry, self.asset_account, 15)
        create_transaction(in_range_entry, self.liability_account, -15)

        response = self.client.get(
            reverse('reports.views.trial_balance_report'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'reports/trial_balance.html')
        self.assertEqual(response.context['start_date'], first_of_year)
        self.assertEqual(response.context['stop_date'], today)
        self.assertIsInstance(response.context['form'], DateRangeForm)
        self.assertTrue(isinstance(response.context['accounts'], list))
        self.assertTrue(isinstance(response.context['accounts'][0], dict))

        # Balances are value balances so the asset's are flipped
        asset_info = {'name': "Asset Account",
                      'number': "1-00001",
                      'beginning_balance': 25,
                      'total_debits': 0,
                      'total_credits': 15,
                      'net_change': 15,
                      'ending_balance': 10,
                      'url': self.asset_account.get_absolute_url()}

        liability_info = {'name': "Liability Account",
                          'number': "2-00001",
                          'beginning_balance': 25,
                          'total_debits': -15,
                          'total_credits': 0,
                          'net_change': -15,
                          'ending_balance': 10,
                          'url': self.liability_account.get_absolute_url()}

        self.assertEqual(response.context['accounts'],
                         [asset_info, liability_info])

    def test_account_with_no_transactions(self):
        """
        An Account with no Transactions in the date range should return the a
        start balance and end balance of the balance at the beginning of the
        period and a debit/credit total and netchange of 0.
        """
        today = datetime.date.today()
        first_of_year = datetime.date(today.year, 1, 1)

        past_entry = create_entry(first_of_year - datetime.timedelta(days=1),
                                  "Before the default report range")
        create_transaction(past_entry, self.asset_account, -25)
        create_transaction(past_entry, self.liability_account, 25)

        asset_info = {'name': "Asset Account",
                      'number': "1-00001",
                      'beginning_balance': 25,
                      'total_debits': 0,
                      'total_credits': 0,
                      'net_change': 0,
                      'ending_balance': 25,
                      'url': self.asset_account.get_absolute_url()}
        liability_info = {'name': "Liability Account",
                          'number': "2-00001",
                          'beginning_balance': 25,
                          'total_debits': 0,
                          'total_credits': 0,
                          'net_change': 0,
                          'ending_balance': 25,
                          'url': self.liability_account.get_absolute_url()}

        response = self.client.get(
            reverse('reports.views.trial_balance_report'))

        self.assertEqual(response.context['accounts'],
                         [asset_info, liability_info])

    def test_date_range(self):
        """
        A `GET` with valid DateRangeForm data should only use Transactions in
        the submitted date range for calculations.
        """
        start_date = datetime.date(2014, 2, 3)
        stop_date = datetime.date(2014, 5, 3)

        before_range = datetime.date(2014, 1, 12)
        in_range = datetime.date(2014, 3, 25)
        after_range = datetime.date(2014, 9, 22)

        past_entry = create_entry(before_range, "Before the report range")
        create_transaction(past_entry, self.asset_account, -50)
        create_transaction(past_entry, self.liability_account, 50)

        in_range_entry = create_entry(in_range, "In the report range")
        create_transaction(in_range_entry, self.asset_account, 23)
        create_transaction(in_range_entry, self.liability_account, -23)

        future_entry = create_entry(after_range, "After the report range")
        create_transaction(future_entry, self.asset_account, 100)
        create_transaction(future_entry, self.liability_account, -100)

        asset_info = {'name': "Asset Account",
                      'number': "1-00001",
                      'beginning_balance': 50,
                      'total_debits': 0,
                      'total_credits': 23,
                      'net_change': 23,
                      'ending_balance': 27,
                      'url': self.asset_account.get_absolute_url()}
        liability_info = {'name': "Liability Account",
                          'number': "2-00001",
                          'beginning_balance': 50,
                          'total_debits': -23,
                          'total_credits': 0,
                          'net_change': -23,
                          'ending_balance': 27,
                          'url': self.liability_account.get_absolute_url()}

        response = self.client.get(
            reverse('reports.views.trial_balance_report'),
            data={'start_date': start_date,
                  'stop_date': stop_date}
        )

        self.assertEqual(response.context['start_date'], start_date)
        self.assertEqual(response.context['stop_date'], stop_date)
        self.assertEqual(response.context['accounts'],
                         [asset_info, liability_info])

    def test_date_range_fail(self):
        """A `GET` with invalid DateRangeForm data should return any errors."""
        response = self.client.get(
            reverse('reports.views.trial_balance_report'),
            data={'start_date': '10a/2/b98',
                  'stop_date': '11b/1threethree7/bar'})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'start_date',
                             'Enter a valid date.')
        self.assertFormError(response, 'form', 'stop_date',
                             'Enter a valid date.')

    def test_get_account_details(self):
        """The helper function should return the correct information."""
        today = datetime.date.today()
        first_of_year = datetime.date(today.year, 1, 1)

        past_entry = create_entry(first_of_year - datetime.timedelta(days=1),
                                  "Before the default report range")
        create_transaction(past_entry, self.liability_account, -25)
        in_range_entry = create_entry(today, "In the default report range")
        create_transaction(in_range_entry, self.liability_account, 15)

        liability_info = {'name': "Liability Account",
                          'number': "2-00001",
                          'beginning_balance': -25,
                          'total_debits': 0,
                          'total_credits': 15,
                          'net_change': 15,
                          'ending_balance': -10,
                          'url': self.liability_account.get_absolute_url()}

        result = _get_account_details(self.liability_account, first_of_year,
                                      today)

        self.assertEqual(result, liability_info)

    def test_get_account_details_flip_balance(self):
        """
        The helper function should return the correct information if the
        Account is an Asset, Expense or Equity.
        """
        today = datetime.date.today()
        first_of_year = datetime.date(today.year, 1, 1)

        past_entry = create_entry(first_of_year - datetime.timedelta(days=1),
                                  "Before the default report range")
        create_transaction(past_entry, self.asset_account, -25)
        in_range_entry = create_entry(today, "In the default report range")
        create_transaction(in_range_entry, self.asset_account, 15)

        asset_info = {'name': "Asset Account",
                      'number': "1-00001",
                      'beginning_balance': 25,
                      'total_debits': 0,
                      'total_credits': 15,
                      'net_change': 15,
                      'ending_balance': 10,
                      'url': self.asset_account.get_absolute_url()}

        result = _get_account_details(self.asset_account, first_of_year, today)

        self.assertEqual(result, asset_info)
