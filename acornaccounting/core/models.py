"""This module contains abstract models used throughout the application."""
from django.db import models

from accounts.models import Account


class AccountWrapper(models.Model):
    """An abstract wrapper for Account instances.

    This model is used to provide a limited selection of manually curated
    Accounts with Communard-friendly names, for Communard-facing forms - for
    example, Local Store Accounts for Trips and Credit Card Accounts for Credit
    Cards.

    """
    account = models.ForeignKey(Account)
    name = models.CharField(
        max_length=50, blank=True,
        help_text="A name for Communards. Defaults to the Account's Name",
    )

    class Meta(object):
        abstract = True
        ordering = ('name',)

    def __unicode__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Pull the name from the Account if blank."""
        if not self.name and self.account:
            self.name = self.account.name
        super(AccountWrapper, self).save(*args, **kwargs)
