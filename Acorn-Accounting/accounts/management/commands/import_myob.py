'''
Django Accounting Command to import MYOB Accounts and Transactions

Requires all child accounts for a header to be directly underneath the header,
coming before any child headers.

Creates Accounts based on MYOB data, then all Entries/Transactions.

Export Account and Journal entries in MYOB and place in root folder of project.
'''
from datetime import date
from decimal import Decimal
from time import strptime

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.template.defaultfilters import slugify

from accounts.models import Header, Account, Event, JournalEntry, BankReceivingEntry,   \
                            BankSpendingEntry, Transaction


def get_date(date_string):
    return date(*strptime(date_string, "%m/%d/%Y")[:3])


def strip_cur_format(inputstr):
    inputstr = inputstr.replace('$', '').replace(',', '')
    return inputstr.replace('(', '-').replace(')', '')


class Command(BaseCommand):
    args = ''
    help = '''\
    Will created Accounts, Entries and Transactions based on MYOB data.
    ACCOUNTS.TXT and JOURNAL.TXT must in your current working directory.
    All Headers should already be created.
    '''

    def handle(self, *args, **options):
        # fill this dictionary with MYOB acct number => django pk for use in
        # processing JOURNAL.txt
        acct_dict = dict()

        # open accounts file
        if Account.objects.count() == 0:
            with open('./ACCOUNTS.TXT') as f:
                for (counter, line) in enumerate(f):
                    columns = line.split('\t')      # 0: number, 1: name
                                                    # 2: header, 3:balance
                    if 'H' in columns[2]:   # is header
                        current_header = Header.objects.get(
                                slug=slugify(columns[1]))
                    else:   # create an account under the current header
                        number = columns[0].replace('-', '')    # strip the `-`
                                                    # between number and type
                        balance = Decimal(strip_cur_format(columns[3]))
                        acc_type = columns[0][0]
                        if int(acc_type) in (1, 5, 6, 8):
                            balance *= -1
                        # check if slug or name is taken
                        name = columns[1]
                        slug = slugify(name)
                        quer = Account.objects.filter(Q(name=name) |
                                Q(slug=slug))
                        if quer.exists():
                            name = name + str(counter)
                            slug = slugify(name)

                        acct = Account.objects.create(parent=current_header,
                                name=name, slug=slug, balance=balance)
                        acct_dict[number] = acct.pk

        # Now create Entries and Transactions
        if Transaction.objects.count() == 0:
            with open('./JOURNAL.TXT') as f:
                last_entry = None
                last_type = None
                for (counter, line) in enumerate(f):
                    if line == '\r\n':
                        # blank lines mean new entries
                        last_entry = None
                        last_type = None
                    else:
                        columns = line.split('\t')  # 0: number, 1: date
                                                    # 2: memo, 3: myob acct num
                                                    # 4: debit, 5: credit
                                                    # 6: job
                        # Derive Event and Balance Delta
                        if len(columns) >= 7 and columns[6] != '':
                            # Event present
                            event = Event.objects.get(number=columns[6])
                        else:
                            event = None
                        if columns[2].lower() == 'void':
                            balance_delta = Decimal(0)
                        elif len(columns) >= 5 and columns[4] == '':
                            # Delta is a credit
                            if columns[5] != '':
                                balance_delta = Decimal(
                                        strip_cur_format(columns[5]))
                            else:
                                balance_delta = 0
                        elif columns[4] != '':
                            # Delta is debit
                            balance_delta = -1 * Decimal(
                                    strip_cur_format(columns[4]))
                        else:
                            balance_delta = 0
                        date = get_date(columns[1])
                        if columns[2] == '':
                            columns[2] = date
                        else:
                            columns[2] = columns[2][:60]

                        if not last_entry:
                            # create new entry
                            entry_num = columns[0]
                            # first 2 chars will be GJ for gen
                            # CR for bank rec, ## or 2 ints for bank spend
                            if entry_num[:2] == 'GJ':
                                # gen entry
                                last_type = 'GJ'
                                last_entry = JournalEntry.objects.create(
                                        date=date,
                                        memo=columns[2])
                                Transaction.objects.create(
                                        journal_entry=last_entry,
                                        balance_delta=balance_delta,
                                        event=event,
                                        account_id=acct_dict[columns[3]])
                            elif entry_num[:2] == 'CR':
                                # bank receive
                                last_type = 'CR'
                                main_transaction = Transaction.objects.create(
                                        account_id=acct_dict[columns[3]],
                                        balance_delta=balance_delta)
                                last_entry = BankReceivingEntry.objects.create(
                                        main_transaction=main_transaction,
                                        memo=columns[2],
                                        date=date,
                                        payor=str(columns[2])[:50])
                            else:                           # bank spend
                                last_type = 'CD'
                                ach = entry_num[:2] == '##'  # if ach payment
                                                    # first two chars is `##`
                                if ach:
                                    main_transaction = Transaction.objects.create(
                                            account_id=acct_dict[columns[3]],
                                            balance_delta=balance_delta)
                                    last_entry = BankSpendingEntry.objects.create(
                                            main_transaction=main_transaction,
                                            memo=columns[2],
                                            date=date,
                                            ach_payment=True)
                                else:
                                    account_id = acct_dict[columns[3]]
                                    check_taken = (
                                    BankSpendingEntry.objects.filter(
                                        check_number=entry_num,
                                        main_transaction__account=account_id
                                        ).exists()
                                    )
                                    if check_taken:
                                        continue
                                    if balance_delta == 0:
                                        main_transaction = Transaction.objects.create(
                                                account_id=acct_dict[columns[3]],
                                                balance_delta=balance_delta)
                                        last_entry = BankSpendingEntry.objects.create(
                                                main_transaction=main_transaction,
                                                memo=columns[2],
                                                date=date,
                                                check_number=entry_num,
                                                void=True)
                                    else:
                                        main_transaction = Transaction.objects.create(
                                                account_id=acct_dict[columns[3]],
                                                balance_delta=balance_delta)
                                        last_entry = BankSpendingEntry.objects.create(
                                                main_transaction=main_transaction,
                                                memo=columns[2],
                                                date=date,
                                                check_number=entry_num)
                        else:
                            # entry already created, just add a Transaction
                            if last_type == 'GJ':
                                Transaction.objects.create(
                                        journal_entry=last_entry,
                                        balance_delta=balance_delta,
                                        event=event,
                                        account_id=acct_dict[columns[3]])
                            elif last_type == 'CR':
                                Transaction.objects.create(
                                        bankreceive_entry=last_entry,
                                        balance_delta=balance_delta,
                                        event=event,
                                        account_id=acct_dict[columns[3]])
                            else:
                                Transaction.objects.create(
                                        bankspend_entry=last_entry,
                                        balance_delta=balance_delta,
                                        event=event,
                                        account_id=acct_dict[columns[3]])
