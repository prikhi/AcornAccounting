"""Test the Import Bank Statement Functionality."""
import datetime
from decimal import Decimal
import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.urlresolvers import reverse
from django.test import TestCase

from accounts.models import Account
from core.tests import create_header, create_account, create_and_login_user
from entries.models import Transaction, BankReceivingEntry, BankSpendingEntry

from bank_import import views
from .forms import (BankAccountForm, TransferImportFormSet,
                    ReceivingImportFormSet, SpendingImportFormSet)
from .importers.vcb import CSVImporter
from .importers.city_first_dc import QFXImporter as CFDCImporter
from .models import BankAccount, CheckRange


class BankAccountModelTests(TestCase):
    """Test the ``BankAccount`` model."""

    def test_get_importer_returns_imported_class(self):
        """Test that `get_importer_class` returns the correct class."""
        header = create_header('Assets')
        account = create_account('Account', header, 0, 0, True)
        bank_account = BankAccount.objects.create(
            account=account, bank=BankAccount.VCB_CSV_IMPORTER)
        self.assertEqual(bank_account.get_importer_class(), CSVImporter)


class QFXImporterTests(TestCase):
    """Test the QFX Importer Classes."""

    def test_city_bank_of_dc_importer(self):
        qfx_text = u"""
OFXHEADER: 100
DATA: OFXSGML
VERSION: 102
SECURITY: NONE
ENCODING: USASCII
CHARSET: 1252
COMPRESSION: NONE
OLDFILEUID: NONE
NEWFILEUID: NONE

<OFX>
  <BANKMSGSRSV1>
    <STMTTRNRS>
      <TRNUID>0</TRNUID>
      <STMTRS>
        <CURDEF>USD</CURDEF>
        <BANKTRANLIST>
          <DTSTART>20161024040000.000[0:GMT]</DTSTART>
          <DTEND>20161206050000.000[0:GMT]</DTEND>
          <STMTTRN>
            <TRNTYPE>CHECK</TRNTYPE>
            <DTPOSTED>20161205050000.000[0:GMT]</DTPOSTED>
            <TRNAMT>-706.00</TRNAMT>
            <FITID>whoopdedoo2</FITID>
            <CHECKNUM>716</CHECKNUM>
            <NAME>Check           716</NAME>
            <MEMO>Check           716</MEMO>
          </STMTTRN>
          <STMTTRN>
            <TRNTYPE>DEBIT</TRNTYPE>
            <DTPOSTED>20161205050000.000[0:GMT]</DTPOSTED>
            <TRNAMT>-67.25</TRNAMT>
            <FITID>whoopdedoo</FITID>
            <NAME>POS Purchase Non-PIN OUT OF ORDE</NAME>
            <MEMO>POS Purchase Non-PIN OUT OF ORDER GAMES OUTOFORDERGAM CA 00000INC100 *****8191 12/02 13:58        </MEMO>
          </STMTTRN>
          <STMTTRN>
            <TRNTYPE>CREDIT</TRNTYPE>
            <DTPOSTED>20161205050000.000[0:GMT]</DTPOSTED>
            <TRNAMT>35.48</TRNAMT>
            <FITID>woopdedoo3</FITID>
            <NAME>POS Purchase Return - PIN LOGAN </NAME>
            <MEMO>POS Purchase Return - PIN LOGAN HARDWARE WASHINGTON DC 0000000006063 *****8191 12/02 04:33        </MEMO>
          </STMTTRN>
        </BANKTRANLIST>
      </STMTRS>
    </STMTTRNRS>
  </BANKMSGSRSV1>
</OFX>
        """
        qfx_file = io.StringIO(qfx_text)
        importer = CFDCImporter(qfx_file)
        data = importer.get_data()

        self.assertEqual(len(data), 3)
        print(data)
        self.assertSequenceEqual(
            data,
            [
                {
                    'date': datetime.datetime(2016, 12, 5, 5),
                    'check_number': '716',
                    'amount': Decimal("-706.00"),
                    'memo': 'Check 716',
                    'type': 'withdrawal'
                },
                {
                    'date': datetime.datetime(2016, 12, 5, 5),
                    'check_number': '0',
                    'amount': Decimal("-67.25"),
                    'memo': 'OUT OF ORDER GAMES OUTOFORDERGAM CA',
                    'type': 'withdrawal'
                },
                {
                    'date': datetime.datetime(2016, 12, 5, 5),
                    'check_number': '',
                    'amount': Decimal("35.48"),
                    'memo': 'LOGAN HARDWARE WASHINGTON DC',
                    'type': 'deposit'
                },

            ]
        )


class MatchTransactionsTests(TestCase):
    """Test the ``views._match_transactions`` function."""

    def setUp(self):
        """Create an Account and an Entry of each type."""
        self.header = create_header('Assets')
        self.account = create_account('Account', self.header, 0, 0, True)
        self.bank_account = BankAccount.objects.create(account=self.account)
        self.day = datetime.date(2014, 4, 20)

        self.deposit_transfer = Transaction.objects.create(
            account=self.account, balance_delta=-30, date=self.day)
        self.withdrawal_transfer = Transaction.objects.create(
            account=self.account, balance_delta=30, date=self.day)
        self.deposit_transaction = Transaction.objects.create(
            account=self.account, balance_delta=-20)
        self.deposit = BankReceivingEntry.objects.create(
            main_transaction=self.deposit_transaction,
            memo='deposit memo', payor='payor', date=self.day)
        self.withdrawal_transaction = Transaction.objects.create(
            account=self.account, balance_delta=20)
        self.withdrawal = BankSpendingEntry.objects.create(
            main_transaction=self.withdrawal_transaction, date=self.day,
            memo='withdrawal memo', payee='payee', ach_payment=True)

    def test_match_from_ach(self):
        """Test that check_number of 0 matches against ACH Payments."""
        data = {'check_number': '0', 'date': self.day, 'type': 'withdrawal',
                'amount': 20}
        (matched, unmatched) = views._match_transactions(
            self.bank_account, [data])
        self.assertSequenceEqual(unmatched, [])
        self.assertSequenceEqual(matched, [self.withdrawal_transaction])

    def test_match_from_check(self):
        """Test that the check_number is matched against Payments."""
        self.withdrawal.ach_payment = False
        self.withdrawal.check_number = '42'
        self.withdrawal.save()

        data = {'check_number': '42', 'date': self.day, 'type': 'withdrawal',
                'amount': 20}
        (matched, unmatched) = views._match_transactions(
            self.bank_account, [data])
        self.assertSequenceEqual(unmatched, [])
        self.assertSequenceEqual(matched, [self.withdrawal_transaction])

    def test_match_from_deposit(self):
        """Test that a Deposit's amount is correctly matched."""
        data = {'check_number': '', 'date': self.day, 'type': 'deposit',
                'amount': 20}
        (matched, unmatched) = views._match_transactions(
            self.bank_account, [data])
        self.assertSequenceEqual(unmatched, [])
        self.assertSequenceEqual(matched, [self.deposit_transaction])

    def test_match_from_transfer_deposit(self):
        """Test that a Transfer Deposit's amount is correctly matched."""
        data = {'check_number': '', 'date': self.day, 'type':
                'transfer_deposit', 'amount': 30}
        (matched, unmatched) = views._match_transactions(
            self.bank_account, [data])
        self.assertSequenceEqual(unmatched, [])
        self.assertSequenceEqual(matched, [self.deposit_transfer])

    def test_match_from_transfer_withdrawal(self):
        """Test that a Transfer Withdrawal's amount is correctly matched."""
        data = {'check_number': '', 'date': self.day, 'type':
                'transfer_withdrawal', 'amount': 30}
        (matched, unmatched) = views._match_transactions(
            self.bank_account, [data])
        self.assertSequenceEqual(unmatched, [])
        self.assertSequenceEqual(matched, [self.withdrawal_transfer])

    def test_date_fuzzed_match(self):
        """Test that dates within a week are correctly matched."""
        time_diff = datetime.timedelta(days=7)
        data = {'check_number': '', 'date': self.day - time_diff,
                'type': 'deposit', 'amount': 20}
        (matched, unmatched) = views._match_transactions(
            self.bank_account, [data])
        self.assertSequenceEqual(unmatched, [])
        self.assertSequenceEqual(matched, [self.deposit_transaction])

    def test_unmatched_are_returned(self):
        """Test that unmatched lines are returned correctly."""
        data = {'check_number': '', 'date': self.day, 'type': 'deposit',
                'amount': 50}
        (matched, unmatched) = views._match_transactions(
            self.bank_account, [data])
        self.assertSequenceEqual(unmatched, [data])
        self.assertSequenceEqual(matched, [])

    def test_items_matched_only_once(self):
        """Test that an existing Transaction is only matched Once."""
        data = {'check_number': '', 'date': self.day, 'type': 'deposit',
                'amount': 20}
        (matched, unmatched) = views._match_transactions(
            self.bank_account, [data, data])
        self.assertSequenceEqual(unmatched, [data])
        self.assertSequenceEqual(matched, [self.deposit_transaction])


class BuildTransferTests(TestCase):
    """Test the ``views._build_transfer`` function."""

    def setUp(self):
        """Create a bank account."""
        self.header = create_header('Assets')
        self.account = create_account('Account', self.header, 0, 0, True)
        self.day = datetime.date(2014, 4, 20)

    def test_deposit_well_formed(self):
        """Test that a transfer deposit has the correct initial data."""
        data = {'amount': 20, 'date': self.day, 'memo': 'something',
                'type': 'transfer_deposit'}
        transfer_data = views._build_transfer(self.account.id, data)

        self.assertIn("amount", transfer_data)
        self.assertIn("date", transfer_data)
        self.assertIn("memo", transfer_data)
        self.assertIn("destination", transfer_data)
        self.assertNotIn("source", transfer_data)

    def test_withdrawal_well_formed(self):
        """Test that a transfer withdrawal has the correct initial data."""
        data = {'amount': 20, 'date': self.day, 'memo': 'something',
                'type': 'transfer_withdrawal'}
        transfer_data = views._build_transfer(self.account.id, data)

        self.assertIn("amount", transfer_data)
        self.assertIn("date", transfer_data)
        self.assertIn("memo", transfer_data)
        self.assertIn("source", transfer_data)
        self.assertNotIn("destination", transfer_data)


class BuildSpendingTests(TestCase):
    """Test the ``views._build_spending`` function."""

    def setUp(self):
        """Add some accounts and an exisiting BankSpendingEntry."""
        self.header = create_header('Assets')
        self.bank_account = create_account(
            'B Account', self.header, 0, 0, True)
        self.wrapper_account = BankAccount.objects.create(
            account=self.bank_account,
            bank='bank_import.importers.vcb.CSVImporter')
        self.expense_account = create_account(
            'E Account', self.header, 0, 6, False)
        self.day = datetime.date(2014, 4, 20)
        self.main_transaction = Transaction.objects.create(
            account=self.bank_account, balance_delta=-50)
        self.entry = BankSpendingEntry.objects.create(
            main_transaction=self.main_transaction, date=self.day, memo="test",
            payee="payee", ach_payment=True)
        Transaction.objects.create(
            bankspend_entry=self.entry, account=self.expense_account,
            balance_delta=50, detail="")

    def test_data_well_formed(self):
        """Test that the returned data has the minimal set of required keys."""
        data = {'amount': 20, 'date': self.day, 'memo': 'hello',
                'check_number': '0'}
        spending_data = views._build_spending(
            self.wrapper_account, self.bank_account.id, data)
        self.assertIn("amount", spending_data)
        self.assertIn("date", spending_data)
        self.assertIn("memo", spending_data)
        self.assertIn("ach_payment", spending_data)
        self.assertTrue(spending_data['ach_payment'])
        self.assertNotIn("check_number", spending_data)

    def test_valid_check_numbers_added(self):
        """Test that a valid check numbe ris added to the data."""
        data = {'amount': 20, 'date': self.day, 'memo': 'hello',
                'check_number': '42'}
        spending_data = views._build_spending(
            self.wrapper_account, self.bank_account.id, data)
        self.assertFalse(spending_data['ach_payment'])
        self.assertIn("check_number", spending_data)
        self.assertEqual(spending_data['check_number'], '42')

    def test_no_memo_doesnt_prefill(self):
        """Test that a deposit with no memo doesn't attempt to prefill."""
        data = {'amount': 20, 'date': self.day, 'memo': '',
                'check_number': '0'}
        spending_data = views._build_spending(
            self.wrapper_account, self.bank_account.id, data)

        self.assertNotIn("payee", spending_data)
        self.assertNotIn("expense_account", spending_data)

    def test_matches_by_memo(self):
        """Test matching by only a memo works correctly."""
        other_date = self.day - datetime.timedelta(days=5)
        data = {'amount': 20, 'date': other_date, 'memo': 'test',
                'check_number': '0'}
        spending_data = views._build_spending(
            self.wrapper_account, self.bank_account.id, data)

        self.assertIn("payee", spending_data)
        self.assertEqual(self.entry.payee, spending_data["payee"])
        self.assertIn("expense_account", spending_data)
        self.assertEqual(
            self.expense_account.id, spending_data["expense_account"])

    def test_memo_and_date_match_preferred(self):
        """Test prefilling from a memo and date match."""
        other_date = self.day - datetime.timedelta(days=5)
        main_transaction = Transaction.objects.create(
            account=self.bank_account, balance_delta=-50)
        entry = BankSpendingEntry.objects.create(
            main_transaction=main_transaction, date=other_date, memo="unique",
            payee="other payee", ach_payment=True)
        Transaction.objects.create(
            bankspend_entry=entry, account=self.expense_account, detail="",
            balance_delta=50)
        data = {'amount': 20, 'date': other_date, 'memo': 'unique',
                'check_number': '0'}
        spending_data = views._build_spending(
            self.wrapper_account, self.bank_account.id, data)

        self.assertIn("payee", spending_data)
        self.assertEqual(spending_data['payee'], 'other payee')
        self.assertIn("expense_account", spending_data)
        self.assertEqual(spending_data['expense_account'],
                         self.expense_account.id)

    def test_matches_check_ranges(self):
        """Test prefilling from a CheckRange match."""
        CheckRange.objects.create(
            bank_account=self.wrapper_account, start_number=25, end_number=42,
            default_account=self.expense_account, default_memo="CR MEMO",
            default_payee="CR PAYEE")
        data = {'amount': 9001, 'date': datetime.date.today(), 'memo': '',
                'check_number': '33'}
        spending_data = views._build_spending(
            self.wrapper_account, self.bank_account.id, data)
        self.assertIn("expense_account", spending_data)
        self.assertEqual(
            spending_data['expense_account'], self.expense_account.id)
        self.assertIn("payee", spending_data)
        self.assertEqual(spending_data['payee'], "CR PAYEE")
        self.assertIn("memo", spending_data)
        self.assertEqual(spending_data['memo'], "CR MEMO")


class BuildReceivingTests(TestCase):
    """Test the ``views._build_receiving`` function."""

    def setUp(self):
        """Add some accounts and an exisiting BankReceivingEntry."""
        self.header = create_header('Initial')
        self.bank_account = create_account(
            'B Account', self.header, 0, 0, True)
        self.income_account = create_account(
            'I Account', self.header, 0, 4, False)
        self.day = datetime.date(2014, 4, 20)
        self.main_transaction = Transaction.objects.create(
            account=self.bank_account, balance_delta=50)
        self.entry = BankReceivingEntry.objects.create(
            main_transaction=self.main_transaction, date=self.day, memo="test",
            payor="payor")
        Transaction.objects.create(
            bankreceive_entry=self.entry, account=self.income_account,
            balance_delta=-50, detail="")

    def test_data_well_formed(self):
        """Test that the returned data has the minimal set of required keys."""
        data = {'amount': 20, 'date': self.day, 'memo': 'hello'}
        receiving_data = views._build_receiving(self.bank_account.id, data)
        self.assertIn("amount", receiving_data)
        self.assertIn("memo", receiving_data)
        self.assertIn("account", receiving_data)
        self.assertIn("date", receiving_data)

    def test_no_memo_doesnt_prefill(self):
        """Test that a deposit with no memo doesn't attempt to prefill."""
        data = {'amount': 20, 'date': self.day, 'memo': ''}
        receiving_data = views._build_receiving(self.bank_account.id, data)

        self.assertNotIn("payor", receiving_data)
        self.assertNotIn("receiving_account", receiving_data)

    def test_matches_by_memo(self):
        """Test matching by only a memo works fine."""
        other_date = self.day - datetime.timedelta(days=5)
        data = {'amount': 20, 'date': other_date, 'memo': 'test'}
        receiving_data = views._build_receiving(self.bank_account.id, data)
        self.assertIn("payor", receiving_data)
        self.assertEqual(receiving_data['payor'], 'payor')
        self.assertIn("receiving_account", receiving_data)
        self.assertEqual(
            receiving_data['receiving_account'], self.income_account.id)

    def test_memo_and_date_match_preferred(self):
        """Test prefilling from a memo and date match."""
        other_date = self.day - datetime.timedelta(days=5)
        main_transaction = Transaction.objects.create(
            account=self.bank_account, balance_delta=50)
        entry = BankReceivingEntry.objects.create(
            main_transaction=main_transaction, date=other_date, memo="test",
            payor="other payor")
        Transaction.objects.create(
            bankreceive_entry=entry, account=self.income_account,
            balance_delta=-50, detail="")

        data = {'amount': 20, 'date': other_date, 'memo': 'test'}
        receiving_data = views._build_receiving(self.bank_account.id, data)
        self.assertIn("payor", receiving_data)
        self.assertEqual(receiving_data['payor'], 'other payor')
        self.assertIn("receiving_account", receiving_data)
        self.assertEqual(receiving_data['receiving_account'],
                         self.income_account.id)


class ImportBankStatementTests(TestCase):
    """Test the ``import_bank_statement`` view."""

    def setUp(self):
        """Create Banks and Income/Expense Accounts."""
        create_and_login_user(self)

        self.asset_header = create_header('asset', cat_type=1)
        self.expense_header = create_header('expense', cat_type=6)
        self.income_header = create_header('income', cat_type=4)
        self.asset_account = create_account(
            'asset', self.asset_header, 0, 1, True)
        self.other_asset = create_account(
            'other asset', self.asset_header, 0, 1, True)
        self.expense_account = create_account(
            'expense', self.expense_header, 0, 6)
        self.income_account = create_account(
            'income', self.income_header, 0, 4)
        self.bank_account = BankAccount.objects.create(
            account=self.asset_account, bank=BankAccount.VCB_CSV_IMPORTER)

    def test_get_returns_account_form(self):
        """Test that a GET request returns a BankAccountForm."""
        response = self.client.get(
            reverse('bank_import.views.import_bank_statement'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bank_import/import_form.html')
        self.assertIn('import_form', response.context)
        self.assertTrue(isinstance(
            response.context['import_form'], BankAccountForm))
        self.assertFalse(response.context['import_form'].is_bound)

    def test_post_upload_returns_formsets(self):
        """Test a POST with a valid import file returns a set of FormSets."""
        file_content = """
Date,Amount,Transaction Description,Check Number,Reference
06/30/2016,837.23,Check,14151,
06/29/2016,1364.96,ACH Payment,0,Rewards MC
06/24/2016,5369.05,Deposit,0,
06/22/2016,428.00,ACH Deposit,0,SSA TREAS 310 XXSOC SEC
06/14/2016,91000.00,IB Transfer Deposit,0,From DDA xxxxxxxx3701
        """
        response = self.client.post(
            reverse('bank_import.views.import_bank_statement'),
            data={
                'import_file': SimpleUploadedFile(
                    "import.csv", file_content.strip()),
                'bank_account': self.bank_account.id,
                'submit': 'Import'
            })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bank_import/import_form.html')
        self.assertIn('transfer_formset', response.context)
        self.assertTrue(isinstance(
            response.context['transfer_formset'], TransferImportFormSet))
        self.assertIn('withdrawal_formset', response.context)
        self.assertTrue(isinstance(
            response.context['withdrawal_formset'], SpendingImportFormSet))
        self.assertIn('deposit_formset', response.context)
        self.assertTrue(isinstance(
            response.context['deposit_formset'], ReceivingImportFormSet))

    def test_post_invalid_formsets_returns_errors(self):
        """Test a POST with invalid FormSets returns FormSets with errors."""
        response = self.client.post(
            reverse('bank_import.views.import_bank_statement'),
            data={
                'transfer-TOTAL_FORMS': 2,
                'transfer-INITIAL_FORMS': 2,
                'transfer-MAX_NUM_FORMS': 2,
                'transfer-0-date': '/20/2016',
                'transfer-0-source': self.asset_account.id,
                'transfer-0-destination': self.other_asset.id,
                'transfer-0-memo': '',
                'transfer-0-amount': 20,
                'transfer-1-date': '04/20/2016',
                'transfer-1-source': self.other_asset.id,
                'transfer-1-destination': self.asset_account.id,
                'transfer-1-memo': 'Valid Entry',
                'transfer-1-amount': 25,
                'withdrawal-TOTAL_FORMS': 2,
                'withdrawal-INITIAL_FORMS': 2,
                'withdrawal-MAX_NUM_FORMS': 2,
                'withdrawal-0-date': '04/20/2016',
                'withdrawal-0-account': self.asset_account.id,
                'withdrawal-0-expense_account': self.expense_account.id,
                'withdrawal-0-memo': '',
                'withdrawal-0-amount': 20,
                'withdrawal-0-ach_payment': True,
                'withdrawal-0-check_number': '',
                'withdrawal-0-payee': '',
                'withdrawal-1-date': '04/20/2016',
                'withdrawal-1-account': self.other_asset.id,
                'withdrawal-1-expense_account': self.expense_account.id,
                'withdrawal-1-memo': 'Valid Entry',
                'withdrawal-1-amount': 25,
                'withdrawal-1-ach_payment': False,
                'withdrawal-1-check_number': '42',
                'withdrawal-1-payee': 'Valid Entry',
                'deposit-TOTAL_FORMS': 1,
                'deposit-INITIAL_FORMS': 1,
                'deposit-MAX_NUM_FORMS': 1,
                'deposit-0-date': '04/20/2016',
                'deposit-0-account': self.asset_account.id,
                'deposit-0-receiving_account': self.income_account.id,
                'deposit-0-memo': 'Invalid - No Payor',
                'deposit-0-amount': 20,
                'deposit-0-payor': '',
                'submit': 'Save',
            })

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bank_import/import_form.html')
        self.assertFalse(response.context['transfer_formset'].is_valid())
        self.assertFalse(response.context['withdrawal_formset'].is_valid())
        self.assertFalse(response.context['deposit_formset'].is_valid())

    def test_post_formsets_success(self):
        """Test a POST with valid FormSets redirects to the Import page."""
        response = self.client.post(
            reverse('bank_import.views.import_bank_statement'),
            data={
                'transfer-TOTAL_FORMS': 2,
                'transfer-INITIAL_FORMS': 2,
                'transfer-MAX_NUM_FORMS': 2,
                'transfer-0-date': '04/20/2016',
                'transfer-0-source': self.asset_account.id,
                'transfer-0-destination': self.other_asset.id,
                'transfer-0-memo': 'Memo Memo',
                'transfer-0-amount': 20,
                'transfer-1-date': '04/20/2016',
                'transfer-1-source': self.other_asset.id,
                'transfer-1-destination': self.asset_account.id,
                'transfer-1-memo': 'Valid Entry',
                'transfer-1-amount': 25,
                'withdrawal-TOTAL_FORMS': 2,
                'withdrawal-INITIAL_FORMS': 2,
                'withdrawal-MAX_NUM_FORMS': 2,
                'withdrawal-0-date': '04/20/2016',
                'withdrawal-0-account': self.asset_account.id,
                'withdrawal-0-expense_account': self.expense_account.id,
                'withdrawal-0-memo': 'Valid Withdrawal 1',
                'withdrawal-0-amount': 20,
                'withdrawal-0-ach_payment': True,
                'withdrawal-0-check_number': '',
                'withdrawal-0-payee': 'Payee 24',
                'withdrawal-1-date': '04/20/2016',
                'withdrawal-1-account': self.asset_account.id,
                'withdrawal-1-expense_account': self.expense_account.id,
                'withdrawal-1-memo': 'Valid Withdrawl 2',
                'withdrawal-1-amount': 25,
                'withdrawal-1-ach_payment': False,
                'withdrawal-1-check_number': '42',
                'withdrawal-1-payee': 'Payee',
                'deposit-TOTAL_FORMS': 1,
                'deposit-INITIAL_FORMS': 1,
                'deposit-MAX_NUM_FORMS': 1,
                'deposit-0-date': '04/20/2016',
                'deposit-0-account': self.asset_account.id,
                'deposit-0-receiving_account': self.income_account.id,
                'deposit-0-memo': 'Valid Deposit',
                'deposit-0-amount': 20,
                'deposit-0-payor': 'Required',
                'submit': 'Save',
            })

        self.assertRedirects(
            response, reverse('bank_import.views.import_bank_statement'))

        self.asset_account = Account.objects.get(id=self.asset_account.id)
        self.assertEqual(self.asset_account.get_balance(), Decimal("-20"))
        self.other_asset = Account.objects.get(id=self.other_asset.id)
        self.assertEqual(self.other_asset.get_balance(), Decimal("-5"))
        self.expense_account = Account.objects.get(id=self.expense_account.id)
        self.assertEqual(self.expense_account.get_balance(), Decimal("45"))
        self.income_account = Account.objects.get(id=self.income_account.id)
        self.assertEqual(self.income_account.get_balance(), Decimal("20"))
