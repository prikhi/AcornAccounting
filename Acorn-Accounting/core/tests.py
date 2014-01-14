from django.template.defaultfilters import slugify
from django.test import TestCase

from accounts.models import Header, Account
from entries.models import JournalEntry, Transaction

from .templatetags.core_filters import capitalize_words


def create_header(name, parent=None, cat_type=2):
    return Header.objects.create(name=name, parent=parent, type=cat_type,
                                 slug=slugify(name))


def create_account(name, parent, balance, cat_type=2, bank=False):
    return Account.objects.create(name=name, slug=slugify(name), parent=parent,
                                  balance=balance, type=cat_type, bank=bank)


def create_entry(date, memo):
    return JournalEntry.objects.create(date=date, memo=memo)


def create_transaction(entry, account, delta):
    return Transaction.objects.create(journal_entry=entry, account=account,
                                      detail=entry.memo, balance_delta=delta)


class CoreFilterTests(TestCase):
    """
    These test the core_filters.
    """

    def test_capitalize_words_all_lower_case(self):
        """A lowercase word should have its first letter capitalized."""
        lowercase_string = "foobar"
        capitalized_string = capitalize_words(lowercase_string)
        self.assertEqual(capitalized_string, "Foobar")

    def test_capitalize_words_an_upper_case_letter(self):
        """A word with an uppercase letter will not be capitalized."""
        uppercase_string = "fooBar"
        uncapitalized_string = capitalize_words(uppercase_string)
        self.assertEqual(uncapitalized_string, "fooBar")

    def test_capitalize_wods_multiple_words(self):
        """These rules apply on a per-word basis, not globally."""
        mixed_sentence = "some oF these WorDs won'T be Capitalized."
        mixed_result = capitalize_words(mixed_sentence)
        self.assertEqual(mixed_result,
                         "Some oF These WorDs won'T Be Capitalized.")
