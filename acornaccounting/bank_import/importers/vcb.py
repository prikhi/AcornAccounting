"""Implements the Importers for Virginia Community Bank."""
import bank_import.importers.base as base


class CSVImporter(base.CSVImporter):
    """Specify the Field Conversion & Type Conversion for VCB CSV Exports."""

    CSV_TO_DATA_FIELDS = {
        'Date': 'date',
        'Amount': 'amount',
        'Transaction Description': 'type',
        'Check Number': 'check_number',
        'Reference': 'memo',
    }

    CSV_TYPE_TO_DATA_TYPE = {
        'ACH Deposit': 'deposit',
        'Accr Earning Pymt': 'deposit',
        'ACH Payment': 'withdrawal',
        'Check': 'withdrawal',
        'Withdrawal': 'withdrawal',
        'Virtual Item W/D': 'withdrawal',
        'Overdraft Fee': 'withdrawal',
        'Stop Pmt Charge': 'withdrawal',
        'Deposit': 'deposit',
        'Deposit Item Ret': 'withdrawal',
        'Dep Item Ret Chrg': 'withdrawal',
        'IB Transfer Deposit': 'transfer_deposit',
        'IB Transfer W/D': 'transfer_withdrawal',
    }

    CSV_FIELD_ORDER = [
        'Account',
        'Date',
        'Amount',
        'Check Number',
        'Reference',
        'Transaction Description',
    ]

    def get_data(self):
        """Reverse the data, imported lines are in descending order by date."""
        self.data.reverse()
        return self.data
