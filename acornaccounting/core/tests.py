from django.contrib.auth.models import User
from django.template.defaultfilters import slugify
from django.test import TestCase

from accounts.models import Header, Account
from entries.models import JournalEntry, Transaction

from .models import AccountWrapper
from .templatetags.core_filters import capitalize_words


def create_header(name, parent=None, cat_type=2):
    """Return a newly created Header."""
    return Header.objects.create(name=name, parent=parent, type=cat_type,
                                 slug=slugify(name))


def create_account(name, parent, balance, cat_type=2, bank=False):
    """Return a newly created Account."""
    return Account.objects.create(name=name, slug=slugify(name), parent=parent,
                                  balance=balance, type=cat_type, bank=bank)


def create_entry(date, memo):
    """Return a newly created JournalEntry."""
    return JournalEntry.objects.create(date=date, memo=memo)


def create_transaction(entry, account, delta):
    """Return a newly created Transaction."""
    return Transaction.objects.create(journal_entry=entry, account=account,
                                      detail=entry.memo, balance_delta=delta)


def create_and_login_user(test_instance):
    """Create a normal user and log them in."""
    password = 'mypassword'
    test_admin = User.objects.create_user('test_user',
                                          'test@test.com',
                                          password)
    test_instance.client.login(username=test_admin.username, password=password)


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


class ConcreteAccountWrapper(AccountWrapper):
    """A simple concrete class to test the abstract AccountWrapper class."""


class AccountWrapperTests(TestCase):
    """
    Test the abstract AccountWrapper model.
    """

    def setUp(self):
        """Create an initial Account."""
        self.header = create_header("Credit Cards", None, 2)
        self.account = create_account("Darmok's CC", self.header, 0, 2)

    def test_name_defaults_to_account_name(self):
        """If the name is left blank it should be filled using the Account."""
        obj = ConcreteAccountWrapper(account=self.account)
        self.assertEqual(obj.name, '')

        obj.save()
        self.assertEqual(obj.name, self.account.name)
