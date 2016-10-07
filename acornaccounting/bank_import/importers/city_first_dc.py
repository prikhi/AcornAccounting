"""Implements the Importers for City First - Bank of DC."""
import re

import bank_import.importers.base as base

MEMO_CLEANING_REGEX = re.compile(r'^(.*?)( [\w\d]+ \S+ .{11})?$')


class QFXImporter(base.QFXImporter):
    """Clean up the memo field."""

    def clean_memo(self, memo):
        memo_regex = MEMO_CLEANING_REGEX.search(memo)
        if memo_regex:
            memo = memo_regex.group(1)

        removals = [
            'POS Purchase Non-PIN',
            'POS Purchase Return - PIN'
        ]
        for removal in removals:
            memo = memo.replace(removal, '').strip()
        return memo
