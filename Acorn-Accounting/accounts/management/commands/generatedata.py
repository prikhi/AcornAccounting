import datetime
import random

from django.core.management.base import BaseCommand
from accounts.models import Header, Account, Transaction, JournalEntry, BankSpendingEntry, BankReceivingEntry


def get_random_account():
    return Account.objects.all()[random.randint(0, 9)]


def get_random_bank():
    return Account.banks.all()[random.randint(0, 1)]


class Command(BaseCommand):
    args = ''
    help = 'Generate mass random data'

    def handle(self, *args, **options):
        if Header.objects.count() == 0:
            asset_head = Header.objects.create(name='Asset', type=1, slug='asset')
            fixed_asset = Header.objects.create(name='Fixed-Asset', slug='fixed-asset', parent=asset_head)
            bank_accounts = Header.objects.create(name='Bank Accounts', slug='bank-accounts', parent=fixed_asset)
            liabilities = Header.objects.create(name='Liabilities', type=2, slug='liability')
            stipends = Header.objects.create(name='Member Stipends', slug='member-stipends', parent=liabilities)
            expense = Header.objects.create(name='Expense', type=6, slug='expense')
            misc_expense = Header.objects.create(name='Misc Expenses', slug='misc-expense', parent=expense)

            Account.objects.create(name='Heartwood', balance=0, slug='heartwood', parent=fixed_asset)
            Account.objects.create(name='VCB Checking', bank=True, balance=0, slug='vcb-checking', parent=bank_accounts)
            Account.objects.create(name='VCB Savings', bank=True, balance=0, slug='vcb-savings', parent=bank_accounts)
            Account.objects.create(name='Pavans Stipend', balance=0, slug='pavans-stipend', parent=stipends)
            Account.objects.create(name='Pauls Stipend', balance=0, slug='pauls-stipend', parent=stipends)
            Account.objects.create(name='Jesus Stipend', balance=0, slug='jesus-stipend', parent=stipends)
            Account.objects.create(name='Quetzl Stipend', balance=0, slug='quetzl-stipend', parent=stipends)
            Account.objects.create(name='Heyzeus Stipend', balance=0, slug='heyzeus-stipend', parent=stipends)
            Account.objects.create(name='Domestic Cleaning', balance=0, slug='domestic-cleaning', parent=misc_expense)
            Account.objects.create(name='Aliens and shit yo', balance=0, slug='alien-yo', parent=misc_expense)
        start_time = datetime.datetime.now()
        for day in range(0, 366):
            print "Starting day {} of 366".format(day)
            date = datetime.date.today() + datetime.timedelta(days=day)
            for GJ in range(0,3):
                entry = JournalEntry.objects.create(date=date, memo='test entry')
                amt1 = random.randint(100, 80000)
                amt2 = random.randint(100, 80000)
                Transaction.objects.create(journal_entry=entry, account=get_random_account(), balance_delta=amt1)
                Transaction.objects.create(journal_entry=entry, account=get_random_account(), balance_delta=amt1 * -1)
                Transaction.objects.create(journal_entry=entry, account=get_random_account(), balance_delta=amt2)
                Transaction.objects.create(journal_entry=entry, account=get_random_account(), balance_delta=amt2 * -1)
            for CD in range(0, 3):
                amt1 = random.randint(100, 80000)
                amt2 = random.randint(100, 80000)

                main_transaction = Transaction.objects.create(account=get_random_bank(), balance_delta=amt1 + amt2)
                entry = BankSpendingEntry.objects.create(date=date, memo='test bank spend', main_transaction=main_transaction)
                Transaction.objects.create(bankspend_entry=entry, account=get_random_account(), balance_delta=amt1 * -1)
                Transaction.objects.create(bankspend_entry=entry, account=get_random_account(), balance_delta=amt2 * -1)
            for CR in range(0, 3):
                amt1 = random.randint(100, 80000)
                amt2 = random.randint(100, 80000)

                main_transaction = Transaction.objects.create(account=get_random_bank(), balance_delta=-1 * (amt1 + amt2))
                entry = BankReceivingEntry.objects.create(date=date, memo='test bank receive', main_transaction=main_transaction)
                Transaction.objects.create(bankreceive_entry=entry, account=get_random_account(), balance_delta=amt1)
                Transaction.objects.create(bankreceive_entry=entry, account=get_random_account(), balance_delta=amt2)
        print "Time to Execute: {}".format(datetime.datetime.now() - start_time)
