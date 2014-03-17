import datetime

from django.core.urlresolvers import reverse
from django.test import TestCase

from core.tests import create_header, create_account, create_entry
from entries.models import Transaction

from .models import Event


class EventModelTests(TestCase):
    """Test the Event model."""
    def setUp(self):
        """Create Headers, Accounts and an Event."""
        self.liability_header = create_header('Liability Account')
        self.liability_account = create_account('Liability Account',
                                                self.liability_header, 0)
        self.event = Event.objects.create(name="test", abbreviation="T",
                                          date=datetime.date.today(),
                                          city="Louisa", state="MD")

    def test_get_net_change(self):
        """The get_net_change method returns the sum of all balance_deltas."""
        entry = create_entry(datetime.date.today(), 'reconciled entry')
        Transaction.objects.create(journal_entry=entry,
                                   account=self.liability_account,
                                   balance_delta=25, event=self.event)
        Transaction.objects.create(journal_entry=entry,
                                   account=self.liability_account,
                                   balance_delta=-15, event=self.event)

        self.event = Event.objects.get()
        net_change = self.event.get_net_change()

        self.assertEqual(net_change, 10)

    def test_get_net_change_no_transactions(self):
        """Events with no transactions should return a net change of 0."""

        net_change = self.event.get_net_change()

        self.assertEqual(net_change, 0)

    def test_generate_number(self):
        """The method should return the abbreviation + YY"""
        event_date = datetime.date(2014, 3, 17)
        event = Event(name="test", abbreviation="JUFHNFU", date=event_date,
                      city="Mineral", state="VA")

        number = event._generate_number()

        self.assertEqual(number, "JUFHNFU14")

    def test_generate_number_on_save(self):
        """Events should generate their `number` field on save."""
        event_date = datetime.date(2014, 3, 17)
        event = Event(name="Test Event", abbreviation="TE", date=event_date,
                      city="Mineral", state="VA")

        self.assertEqual(event.number, "")

        event.save()
        event = Event.objects.get(id=event.id)

        self.assertEqual(event.number, "TE14")


class EventDetailViewTests(TestCase):
    """
    Test Event detail view
    """
    def setUp(self):
        """
        Events are tied to Transactions which require an Account.
        """
        self.asset_header = create_header('asset', cat_type=1)
        self.bank_account = create_account(
            'bank', self.asset_header, 0, 1, True)
        self.event = Event.objects.create(
            name='test event', city='mineral', state='VA',
            date=datetime.date.today(), abbreviation="TE")

    def test_show_event_detail_view_initial(self):
        """
        A `GET` to the `show_event_detail` view with a valid `event_id` will
        return the respective `Event`.
        """
        general = create_entry(datetime.date.today(), 'general entry')
        Transaction.objects.create(journal_entry=general, balance_delta=20,
                                   account=self.bank_account, event=self.event)
        Transaction.objects.create(journal_entry=general, balance_delta=20,
                                   account=self.bank_account, event=self.event)

        response = self.client.get(reverse('events.views.show_event_detail',
                                           kwargs={'event_id': self.event.id}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'events/event_detail.html')
        self.assertEqual(response.context['event'], self.event)

    def test_show_event_detail_view_initial_no_transactions(self):
        """
        A `GET` to the `show_event_detail` view with a valid `event_id` will
        return the respective `Event`. If no Transactions exist for this Event,
        all counters should return appropriately.
        """
        response = self.client.get(reverse('events.views.show_event_detail',
                                           kwargs={'event_id': self.event.id}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'events/event_detail.html')
        self.assertEqual(response.context['event'], self.event)
        self.assertEqual(response.context['debit_total'], 0)
        self.assertEqual(response.context['credit_total'], 0)
        self.assertEqual(response.context['net_change'], 0)

    def test_show_event_detail_view_initial_only_credits(self):
        """
        A `GET` to the `show_event_detail` view with a valid `event_id` will
        also return the correct counters for `net_change`, `debit_total` and
        `credit_total` when only credits are present.
        """
        general = create_entry(datetime.date.today(), 'general entry')
        Transaction.objects.create(journal_entry=general, balance_delta=20,
                                   account=self.bank_account, event=self.event)
        Transaction.objects.create(journal_entry=general, balance_delta=20,
                                   account=self.bank_account, event=self.event)

        response = self.client.get(reverse('events.views.show_event_detail',
                                           kwargs={'event_id': self.event.id}))
        self.assertEqual(response.context['debit_total'], 0)
        self.assertEqual(response.context['credit_total'], 40)
        self.assertEqual(response.context['net_change'], 40)

    def test_show_event_detail_view_initial_only_debits(self):
        """
        A `GET` to the `show_event_detail` view with a valid `event_id` will
        also return the correct counters for `net_change`,`debit_total` and
        `credit_total` when only debits are present.
        """
        general = create_entry(datetime.date.today(), 'general entry')
        Transaction.objects.create(journal_entry=general, balance_delta=-20,
                                   account=self.bank_account, event=self.event)
        Transaction.objects.create(journal_entry=general, balance_delta=-20,
                                   account=self.bank_account, event=self.event)

        response = self.client.get(reverse('events.views.show_event_detail',
                                           kwargs={'event_id': self.event.id}))
        self.assertEqual(response.context['debit_total'], -40)
        self.assertEqual(response.context['credit_total'], 0)
        self.assertEqual(response.context['net_change'], -40)

    def test_show_event_detail_view_initial_debit_and_credit(self):
        """
        A `GET` to the `show_event_detail` view with a valid `event_id` will
        also return the correct counters for `net_change`, `debit_total` and
        `credit_total` when credits and debits are present.
        """
        general = create_entry(datetime.date.today(), 'general entry')
        Transaction.objects.create(journal_entry=general, balance_delta=20,
                                   account=self.bank_account, event=self.event)
        Transaction.objects.create(journal_entry=general, balance_delta=-20,
                                   account=self.bank_account, event=self.event)

        response = self.client.get(reverse('events.views.show_event_detail',
                                           kwargs={'event_id': self.event.id}))
        self.assertEqual(response.context['debit_total'], -20)
        self.assertEqual(response.context['credit_total'], 20)
        self.assertEqual(response.context['net_change'], 0)

    def test_show_event_detail_view_fail(self):
        """
        A `GET` to the `show_event_detail` view with an invalid `event_id` will
        return a 404.
        """
        response = self.client.get(reverse('events.views.show_event_detail',
                                           kwargs={'event_id': 90000001}))
        self.assertEqual(response.status_code, 404)
