"""Context processors related to Accounts."""

import json
from accounts.models import (Account)


def all_accounts(request):
    """Inject the `accounts_json` variable into every context.

    This is used to pre-populate every AJAX Account Select widget.

    """
    accounts = Account.objects.order_by('name')
    values = [{'text': account.name,
               'description': account.description,
               'value': account.id} for account in accounts]
    return {'accounts_json': json.dumps(values)}
