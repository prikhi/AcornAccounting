from django.db.models.signals import pre_delete
from django.dispatch.dispatcher import receiver

from .models import Transaction


@receiver(pre_delete, sender=Transaction)
def transaction_delete(sender, instance, **kwargs):
        '''Refunds Transaction before deleting from database.'''
        instance.account.balance = instance.account.balance - instance.balance_delta
        instance.account.save()
