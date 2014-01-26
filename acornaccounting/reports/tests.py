import datetime

from django.core.urlresolvers import reverse
from django.test import TestCase

from core.tests import (create_header, create_account, create_entry,
                        create_transaction)
from entries.models import Transaction
from events.models import Event

from .views import _get_account_details


class EventsReportView(TestCase):
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


class TrialBalanceReportView(TestCase):
    """Test the trial_balance_report view."""
    def setUp(self):
        """Create an Asset and Liability account."""
        asset_header = create_header('Asset Header', cat_type=1)
        self.asset_account = create_account('Asset Account', asset_header, 0)
        liability_header = create_header('Liability Header')
        self.liability_account = create_account('Liability Account',
                                                liability_header, 0)

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
                          'number': "2-0001",
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
                      'number': "1-0001",
                      'beginning_balance': 25,
                      'total_debits': 0,
                      'total_credits': 15,
                      'net_change': 15,
                      'ending_balance': 10,
                      'url': self.asset_account.get_absolute_url()}

        result = _get_account_details(self.asset_account, first_of_year, today)

        self.assertEqual(result, asset_info)

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
        self.assertTrue(isinstance(response.context['accounts'], list))
        self.assertTrue(isinstance(response.context['accounts'][0], dict))

        # Balances are value balances so the asset's are flipped
        asset_info = {'name': "Asset Account",
                      'number': "1-0001",
                      'beginning_balance': 25,
                      'total_debits': 0,
                      'total_credits': 15,
                      'net_change': 15,
                      'ending_balance': 10,
                      'url': self.asset_account.get_absolute_url()}

        liability_info = {'name': "Liability Account",
                          'number': "2-0001",
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
                      'number': "1-0001",
                      'beginning_balance': 25,
                      'total_debits': 0,
                      'total_credits': 0,
                      'net_change': 0,
                      'ending_balance': 25,
                      'url': self.asset_account.get_absolute_url()}
        liability_info = {'name': "Liability Account",
                          'number': "2-0001",
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
                      'number': "1-0001",
                      'beginning_balance': 50,
                      'total_debits': 0,
                      'total_credits': 23,
                      'net_change': 23,
                      'ending_balance': 27,
                      'url': self.asset_account.get_absolute_url()}
        liability_info = {'name': "Liability Account",
                          'number': "2-0001",
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
