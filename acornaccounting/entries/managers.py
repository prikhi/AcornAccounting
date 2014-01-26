from decimal import Decimal

from caching.base import CachingQuerySet
from django.db import models


class TransactionQuerySet(CachingQuerySet):
    """A wrapper for the :class:`caching.base.CachingQuerySet`.

    The methods of this class mimic the :class:`TransactionManager` class. This
    allows the chaining of our custom methods. For example:

        Transaction.objects.filter(id__gt=500).get_totals()

    """
    def get_totals(self, net_change=False):
        """See :meth:`TransactionManager.get_totals`."""
        return _get_totals_from_query_set(self, net_change)


class TransactionManager(models.Manager):
    """A Custom Manager for the :class:`~.models.Transaction` Model.

    .. note::

        Using this Manager as a Model's default Manager will cause this Manager
        to be used when the Model is accessed through Related Fields.

    """
    use_for_related_fields = True

    def get_query_set(self):
        """Return a :class:`caching.base.CachingQuerySet`."""
        return TransactionQuerySet(self.model, using=self._db)

    def get_totals(self, net_change=False):
        # TODO: Flags are generally bad and should be refactored into another
        # funciton (net_change)
        """
        Calculate debit and credit totals for the respective Queryset.

        Groups and Sums the default Queryset by positive/negative
        :attr:`~.models.Transaction.balance_delta`. Totals default to ``0`` if
        no corresponding :class:`~.models.Transaction` is found.

        Optionally:
            * Returns the Net Change(credits + debits) with the totals.

        :param query: Optional Q query used to filter Manager's Queryset.
        :type query: :class:`~django.db.models.Q`
        :param net_change: Calculate the difference between debits and credits.
        :type net_change: bool
        :returns: Debit and credit sums and optionally the net_change.
        :rtype: :obj:`tuple`

        """
        query_set = self.get_query_set()
        return _get_totals_from_query_set(query_set, net_change)


def _get_totals_from_query_set(query_set, net_change):
    """Return the query_sets total debits/credits and optionally net_change."""
    query_set = query_set.values_list('balance_delta')
    debit_total = Decimal(sum(balance_delta[0] for balance_delta in query_set
                          if balance_delta[0] < 0))
    credit_total = Decimal(sum(balance_delta[0] for balance_delta in query_set
                           if balance_delta[0] > 0))
    if net_change:
        return debit_total, credit_total, credit_total + debit_total
    return debit_total, credit_total
