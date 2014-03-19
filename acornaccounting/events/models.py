from caching.base import CachingManager, CachingMixin
from localflavor.us.models import USStateField
from django.core.urlresolvers import reverse
from django.db import models


class Event(CachingMixin, models.Model):
    """Hold information about Events."""
    name = models.CharField(max_length=150)
    abbreviation = models.CharField(max_length=10)
    date = models.DateField()
    city = models.CharField(max_length=50)
    state = USStateField()
    number = models.CharField(max_length=12, blank=True, editable=False)

    objects = CachingManager()

    class Meta:
        """Order Events by Date."""
        ordering = ['date']

    def __unicode__(self):
        return self.number

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
