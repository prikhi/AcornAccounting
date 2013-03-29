from decimal import Decimal

from django.db.models.signals import pre_delete, pre_save
from django.dispatch.dispatcher import receiver

from .models import Account, Transaction, BankSpendingEntry


@receiver(pre_save, sender=Transaction)
def transaction_postsave(sender, instance, **kwargs):
    '''Changes Account balances if Account or balance_delta is changed'''
    if not instance.last_account:
        instance.last_account = instance.account.id

    balance_change = instance.last_delta != instance.balance_delta
    last_account = Account.objects.get(id=instance.last_account)
    account_change = last_account != instance.account
    if balance_change and account_change:
        last_account.balance = last_account.balance - Decimal(instance.last_delta)
        instance.account.balance = instance.account.balance + instance.balance_delta
        instance.last_account = instance.account.id
        instance.last_delta = instance.balance_delta
        last_account.save()
    elif account_change:
        last_account.balance = last_account.balance - instance.balance_delta
        instance.account.balance = instance.account.balance + instance.balance_delta
        instance.last_account = instance.account.id
        last_account.save()
    elif balance_change:
        instance.account.balance = instance.account.balance - Decimal(instance.last_delta) + instance.balance_delta
        instance.last_delta = instance.balance_delta
    instance.account.save()


@receiver(pre_delete, sender=Transaction)
def transaction_delete(sender, instance, **kwargs):
    '''Refunds Transaction before deleting from database.'''
    instance.account.balance = instance.account.balance - instance.balance_delta
    instance.account.save()


@receiver(pre_save, sender=BankSpendingEntry)
def bankspending_presave(sender, instance, **kwargs):
    '''Set Check Number to Null if Entry is an ACH Payment.'''
    if instance.ach_payment:
        instance.check_number = None
