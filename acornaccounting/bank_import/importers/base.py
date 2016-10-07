"""Abstract Classes that Custom Importers Should Inherit From."""
from abc import ABCMeta, abstractmethod
import csv
import datetime
from decimal import Decimal
import re

from ofxparse import OfxParser


class BaseImporter(object):
    """An abstract class for the ``import_bank_statement`` view.

    Descendants of this class handle parsing the ``file_object`` and returning
    the parsed transaction dictionaries.

    """

    __metaclass__ = ABCMeta

    def __init__(self, file_object, *args, **kwargs):
        """Process the passed file_object and set the list of dictionaries."""
        self.data = self.process_file(file_object)

    @abstractmethod
    def process_file(self, file_object):
        """Process the File & Return a list of Dictionaries."""

    def get_data(self):
        """Return the parsed data."""
        return self.data


class CSVImporter(BaseImporter):
    """An abstact Bank Statement Importer to process CSV Files.

    The ``file_object`` passed to the constructor should point to a CSV file
    whose first row are headers for the columns.

    Implementations must specify two class attributes:

        1. ``CSV_TO_DATA_FIELDS`` - a dictionary mapping from CSV column names
           to data field names. Required field names are ``date``, ``amount``,
           ``check_number``, ``type`, & ``memo``.

        1. ``CSV_TYPE_TO_DATA_TYPE`` - a dictionary mapping from CSV type
           column values to data type values. Valid data type values are
           ``transfer_deposit``, ``transfer_withdrawal`, ``deposit``, or
           ``withdrawal``.

    An optional ``CSV_DATE_FORMAT`` class attribute may modify the format
    string used to parse the date field. By default, ``MM/DD/YYYY`` is
    expected.

    """

    CSV_TO_DATA_FIELDS = None
    CSV_TYPE_TO_DATA_TYPE = None
    CSV_DATE_FORMAT = "%m/%d/%Y"

    def process_file(self, file_object):
        """Read the CSV file and Return the Data using CSV_TO_DATA_FIELDS."""
        if None in [self.CSV_TO_DATA_FIELDS, self.CSV_TYPE_TO_DATA_TYPE]:
            raise NotImplementedError()

        reader = csv.DictReader(file_object)
        data = []
        space_reducing_regex = re.compile(r'\s\s+')
        for row in reader:
            item = {}
            for (csv_field, data_field) in self.CSV_TO_DATA_FIELDS.items():
                item[data_field] = row.get(csv_field)
            item['type'] = self.CSV_TYPE_TO_DATA_TYPE[item['type']]
            item['amount'] = Decimal(item['amount'])
            item['memo'] = space_reducing_regex.sub(' ', item['memo'])
            item['date'] = datetime.datetime.strptime(
                item['date'], self.CSV_DATE_FORMAT).date()
            data.append(item)
        return data


class QFXImporter(BaseImporter):
    """A Bank Statement importer to process QFX files.

    Bank-specific implementations of this importer may want to cleanup the memo
    field, by overriding the `clean_memo` function.
    """

    def process_file(self, file_object):
        """Read the QFX file & Return the standardized data."""
        ofx_data = OfxParser.parse(file_object)

        data = []
        space_reducing_regex = re.compile(r'\s\s+')
        for transaction in ofx_data.account.statement.transactions:
            item = {
                'date': transaction.date,
                'check_number': transaction.checknum,
                'memo': space_reducing_regex.sub(
                    ' ', self.clean_memo(transaction.memo)),
                'amount': transaction.amount,
            }
            if transaction.type in ('debit', 'check'):
                item['type'] = 'withdrawal'
                if item['check_number'] == '':
                    item['check_number'] = '0'
            else:
                item['type'] = 'deposit'
            data.append(item)
        return data

    def clean_memo(self, memo):
        """Clean the memo field."""
        return memo
