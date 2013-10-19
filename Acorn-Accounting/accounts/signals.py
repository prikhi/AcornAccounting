from django.db.models import F
from django.db.models.signals import pre_delete, pre_save, post_save
from django.dispatch.dispatcher import receiver

from .models import Header, Account, Transaction


# TODO: Next 2 should be in __save__ methods, pre before super call, post after
@receiver(pre_save, sender=Header)
def header_presave(sender, instance, **kwargs):
    '''Inherit the root Header's type'''
    if not instance.is_root_node():
        instance.type = instance.get_root().type


@receiver(pre_save, sender=Account)
def account_presave(sender, instance, **kwargs):
    '''Inherit the parent Header's type'''
    instance.type = instance.parent.type


@receiver(pre_save, sender=Transaction)
def transaction_presave(sender, instance, **kwargs):
    '''Refund Account balances if updating a Transaction'''
    if instance.id:
        old_instance = Transaction.objects.get(id=instance.id)
        Account.objects.filter(id=old_instance.account.id).update(balance=F('balance') - old_instance.balance_delta)


@receiver(post_save, sender=Transaction)
def transaction_postsave(sender, instance, **kwargs):
    '''Change Account Balance on Save'''
    Account.objects.filter(id=instance.account.id).update(balance=F('balance') + instance.balance_delta)


@receiver(pre_delete, sender=Transaction)
def transaction_delete(sender, instance, **kwargs):
    '''Refunds Transaction before deleting from database.'''
    Account.objects.filter(id=instance.account.id).update(balance=F('balance') - instance.balance_delta)
