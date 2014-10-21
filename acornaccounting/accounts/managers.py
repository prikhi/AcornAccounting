from caching.base import CachingQuerySet
from mptt.models import TreeManager


class AccountManager(TreeManager):
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
