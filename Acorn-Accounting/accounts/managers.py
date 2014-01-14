from caching.base import CachingQuerySet
from mptt.models import TreeManager


class CachingTreeManager(TreeManager):
    """A :class:`~mptt.models.TreeManager` which uses caching.

    This manager uses a :class:`~caching.base.CachingQuerySet` to cache queries
    with django-cache-machine.

    """
    def get_query_set(self):
        return CachingQuerySet(self.model, using=self._db).order_by(
            self.tree_id_attr, self.left_attr)


class AccountManager(CachingTreeManager):
    """
    A Custom Manager for the :class:`Account` Model.

    This class inherits from the :class:`CachingTreeManager`.

    """
    def get_banks(self):
        """This method will return a Queryset containing any Bank Accounts."""
        return self.filter(bank=True)

    def active(self):
        """This method will return a Querset containing all Active Accounts."""
        return self.filter(active=True)
