from decimal import Decimal

from caching.base import CachingManager
from django.db import models


class TransactionManager(CachingManager):
    """A Custom Manager for the :class:`~.models.Transaction` Model.

    Subclass of :class:`caching.base.CachingManager`.

    .. note::

        Using this Manager as a Model's default Manager will cause this Manager
        to be used when the Model is accessed through Related Fields.

    """
    use_for_related_fields = True

    def get_totals(self, query=None, net_change=False):
        # TODO: Flags are generally bad and should be refactored into another
        # funciton (net_change)
        """
        Calculate debit and credit totals for the respective Queryset.

        Groups and Sums the default Queryset by positive/negative
        :attr:`~.models.Transaction.balance_delta`. Totals default to ``0`` if
        no corresponding :class:`~.models.Transaction` is found.

        Optionally:
            * Filters the Manager's Queryset by ``query`` parameter.
            * Returns the Net Change(credits + debits) with the totals.

        :param query: Optional Q query used to filter Manager's Queryset.
        :type query: :class:`~django.db.models.Q`
        :param net_change: Calculate the difference between debits and credits.
        :type net_change: bool
        :returns: Debit and credit sums and optionally the net_change.
        :rtype: :obj:`tuple`

        """
        # TODO: Can we just use `self` for this and filtering `query`?
        base_qs = self.get_query_set()
        if query:
            # TODO: Can we assume the qs has already been filtered?
            base_qs = base_qs.filter(query)
        debit_total = base_qs.filter(models.Q(balance_delta__lt=0)).aggregate(
            models.Sum('balance_delta'))['balance_delta__sum'] or Decimal(0)
        credit_total = base_qs.filter(models.Q(balance_delta__gt=0)).aggregate(
            models.Sum('balance_delta'))['balance_delta__sum'] or Decimal(0)
        if net_change:
            return debit_total, credit_total, credit_total + debit_total
        return debit_total, credit_total
