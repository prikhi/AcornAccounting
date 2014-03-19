from caching.base import CachingManager, CachingMixin
from localflavor.us.models import USStateField
from django.core.urlresolvers import reverse
from django.db import models


class BaseEvent(CachingMixin, models.Model):
    """
    An abstract class for the commonalities of the :class:`Event` and
    :class:`HistoricalEvent` models.

    .. attribute:: name

        The name of the archived :class:`Event`.

    .. attribute:: number

        The number designated to the :class:`Event`. Generated from the
        :class:`Event's<Event>` :attr:`~BaseEvent.date` and
        :attr:`~Event.abbreviation`.

    .. attribute:: date

        The date of the :class:`Event`.

    .. attribute:: city

        The city the :class:`Event` occurred in.

    .. attribute:: state

        The state or region the :class:`Event` occurred in.

    """
    name = models.CharField(max_length=150)
    date = models.DateField()
    city = models.CharField(max_length=50)
    state = USStateField()
    number = models.CharField(max_length=12, blank=True, editable=False)

    class Meta:
        """Order Events by Date."""
        abstract = True
        ordering = ['-date']

    def __unicode__(self):
        return self.number


class Event(BaseEvent):
    """Hold information about Events."""
    abbreviation = models.CharField(max_length=10)

    objects = CachingManager()

    def get_absolute_url(self):
        """Return the URL of the Event's Details Page."""
        return reverse('events.views.show_event_detail',
                       kwargs={'event_id': self.id})

    def save(self, *args, **kwargs):
        """Set the :attr:`number` before saving."""
        self.full_clean()
        self.number = self._generate_number()
        super(Event, self).save(*args, **kwargs)

    def get_net_change(self):
        """Return the sum of all related credit and debit charges.

        :rtype: :class:`~decimal.Decimal`

        """
        _, _, net_change = self.transaction_set.get_totals(net_change=True)
        return net_change

    def _generate_number(self):
        """Combine the `year` and `abbreviation` to generate the number."""
        abbreviation = self.abbreviation.upper()
        year_digits = str(self.date.year)[2:]
        return "{0}{1}".format(abbreviation, year_digits)


class HistoricalEvent(BaseEvent):
    """
    Historical Events record :class:`Events<Event>` that occurred in previous
    :class:`Fiscal Years<fiscalyears.models.FiscalYear>`.

    When a :class:`Fiscal Year<fiscalyears.models.FiscalYear>` is closed, all
    :class:`Transactions<entries.models.Transaction>` from that :class:`Fiscal
    Year<fiscalyears.models.FiscalYear>` are purged. Historical Events preserve
    the state of :class:`Events<Event>` before the purging. They do not save
    the :class:`~entries.models.Transaction` data but rather the overall data
    such as the total number of debits.

    Instances of this model are automatically created by the
    :func:`~fiscalyears.views.add_fiscal_year` view.

    .. attribute:: credit_total

        The total number of Credits related to the :class:`Event`.

    .. attribute:: debit_total

        The total number of Debits related to the :class:`Event`. This value
        should be a negative number.

    .. attribute:: net_change

        The Net Change of all :class:`Transactions
        <entries.models.Transaction>` related to the :class:`Event`.

    """
    credit_total = models.DecimalField(
        help_text="The total amount of Credits related to the Event.",
        max_digits=19, decimal_places=4)
    debit_total = models.DecimalField(
        help_text="The total amount of Credits related to the Event.",
        max_digits=19, decimal_places=4)
    net_change = models.DecimalField(
        help_text="The Net Change of all Transactions related to the Event.",
        max_digits=19, decimal_places=4)

    objects = CachingManager()
