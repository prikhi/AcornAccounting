"""Models related to Bank Accounts & Imports."""
import importlib

from django.db import models

from core.models import AccountWrapper


class BankAccount(AccountWrapper):
    """An Accountant-Visible Wrapper for an :class:`~accounts.models.Account`.

    This lets us keep track of the importer class to use for each Account.

    .. attribute:: account

        The :class:`~accounts.model.Account` the BankAccount is linked to. This
        is the Account that will have it's Entries imported.

    .. attribute:: name

        A name for the Bank Account, used in forms.

    .. attribute:: bank

        The module/function path to the statement importer to use for this
        account.

    """

    VCB_CSV_IMPORTER = 'bank_import.importers.vcb.CSVImporter'
    CF_DC_QFX_IMPORTER = 'bank_import.importers.city_first_dc.QFXImporter'
    BANK_NAMES_TO_IMPORTERS = (
        (VCB_CSV_IMPORTER, 'Virginia Community Bank'),
        (CF_DC_QFX_IMPORTER, 'City First - Bank of DC'),
    )
    bank = models.CharField(
        blank=False, choices=BANK_NAMES_TO_IMPORTERS, max_length=100,
        help_text="The Bank this Account Belongs to. Used for importing data."
    )

    def get_importer_class(self):
        """Import and return the Importer to use for the Bank Account."""
        (module_name, class_name) = self.bank.rsplit(".", 1)
        return getattr(importlib.import_module(module_name), class_name)


class CheckRange(models.Model):
    """Store a Default Account/Memo/Payee for a BankAccount's Checks.

    When importing a bank statement, any expense checks that fall within a
    CheckRange should be pre-filled with the ``default_account``,
    ``default_payee``, & ``default_memo`` of the CheckRange.

    .. attribute:: bank_account

        The :class:`~BankAccount` that the CheckRange applies to.

    .. attribute:: start_number

        The starting check number of the range.

    .. attribute:: end_number

        The ending check number of the range.

    .. attribute:: default_account

        The :class:`~accounts.models.Account` to use for checks that fall
        within the range.

    .. attribute:: default_payee

        The Payee to use for checks that fall within the range.

    .. attribute:: default_memo

        The Memo to use for checks that fall within the range.

    """

    bank_account = models.ForeignKey(BankAccount)

    start_number = models.PositiveIntegerField(
        help_text="The Starting Check Number for this Range."
    )
    end_number = models.PositiveIntegerField(
        help_text="The Ending Check Number for this Range."
    )
    default_account = models.ForeignKey(
        'accounts.Account', on_delete=models.CASCADE,
        help_text="The Default Account to assign to Checks in this Range."
    )
    default_payee = models.CharField(
        max_length=50, blank=True,
        help_text="The Default Payee to assign to Checks in this Range."
    )
    default_memo = models.CharField(
        max_length=60, blank=True,
        help_text="The Default Memo to assign to Checks in this Range.",
    )

    def __unicode__(self, *args, **kwargs):
        return "CheckRange {} - {} to {}".format(
            self.bank_account, self.start_number, self.end_number)
