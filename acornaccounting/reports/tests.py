import datetime

from django.core.urlresolvers import reverse
from django.test import TestCase

from core.tests import create_header, create_account, create_entry
from entries.models import Transaction
from events.models import Event


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

    def test_events_report(self):
        """
        A `GET` to the `events_report` view will retrieve all Events, ordered
        by date.
        """
        response = self.client.get(reverse('reports.views.events_report'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'reports/events.html')
        self.assertSequenceEqual(response.context['events'],
                                 [self.event1, self.event2])

    def test_events_report_no_events(self):
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
