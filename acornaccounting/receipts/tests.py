"""Tests Receipts."""
import datetime

from django.test import TestCase

from core.tests import create_header, create_account, create_entry

from .models import Receipt


class ReceiptModelTests(TestCase):
    """Test the Receipt model."""
    def setUp(self):
        """Create an Entry for the Receipt."""
        self.header = create_header("Expense Header", None, 6)
        self.account = create_account("Darmok's Stipend", self.header, 0, 6)
        self.entry = create_entry(datetime.date.today(), 'Unique New York')

    def test_entry_number_in_representation(self):
        """
        The string representation for the Receipt should contain the Entry's
        number.
        """
        receipt = Receipt.objects.create(journal_entry=self.entry)
        self.assertIn(self.entry.memo, str(receipt))
