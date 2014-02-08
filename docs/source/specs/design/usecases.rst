.. _Use Cases:

Use Cases
===========

.. uml::
    :includegraphics: scale=.55

    left to right direction
    :Accountant: as acc
    :Communard: as com
    :Budgeter: as bud
    acc --|> com : extends
    bud --|> com : extends
    rectangle Accounts {
        com -- (Check Balances)
        acc --- (Reconcile Balance)
        bud -- (View History)
    }

    rectangle Entry {
        com -- (Enter Trips)
        com -- (Enter Credit Cards)
        acc -- (Approve Entries)
        acc -- (Enter Deposits\n& Withdrawls)
        acc --- (Pay Stipends)
        acc -- (Enter Transfers)
        acc --- (View/Edit Details)
    }


.. _Communard Usecases:

Communards
-----------

Communards will use the application to enter Trip and Credit Card purchases,
and check balances for Accounts such as their Stipend, Deposited Asssets and
any related Budgeted Projects.

Communards will take out Cash Advances to make Community and Personal Purchases
in town, known as Trips. Communards will enter their Trips through the
:ref:`Trip Entry Form`. Trips allow Communards to associate Purchases with
their relevant Accounts.

Communards with Personal Credit Cards will use the application enter their
Purchases and associate Purchases with an Account. This will be done with
the help of the :ref:`Credit Card Entry Form`.

A Communard may want to check their Stipend or Deposited Assets Balances, or
review the Purchases and Balance of any Projects they manage. They may check
the current Balance of any Account via the :ref:`Chart of Accounts <Chart of
Accounts Page Design>` and all Debits/Credits to a specific Account via the
:ref:`Account's Detail Page <Account Detail Page Design>`.

.. _Accountant Usecases:

Accountants
-----------

Accountants are Communards but with more responsibilities. They will use the
application like Communards, but will also be involved in additional Entry and
Administration Tasks.

.. uml::
    :includegraphics: scale=.6

    :Accountant: as acc
    rectangle Administration {
        acc -- (Create/Edit Event)
        acc -- (Create/Edit Account)
        acc -- (Start New Fiscal Year)
    }

Accountants will use the :ref:`Add Entry Pages <Add Journal Entry Page Design>`
to enter new Forms and Statements such as Bank and Credit Card Statements or
Internal Transfers. Accountants are responsible for approving Credit Card and
Trip Entries submitted by Communards.

Accountants will also reconcile an Account's balance against a Statement's
balance using the :ref:`Reconcile Account Page <Reconcile Account Page
Design>`.

Occasionally they will change an Account, Entry or Event's details and create
new Accounts and Events. This can be as simple as fixing a spelling error or as
destructive as deleting an Account. Accounts and Events are editable through
their respective :ref:`Admin Pages <Admin Pages Design>`. Entries are created
and edited through their respective :ref:`Add Entry Page <Add Journal Entry
Page Design>`.

Once a Year, Accountants will start a new Fiscal Year. Fiscal Years allow
Accountants to archive a Year's data, removing old entries and resetting
Account balances in order to track spending and income on a yearly basis.
Fiscal Year creation will be handled by the :ref:`Add Fiscal Year Page <Add
Fiscal Year Page Design>`.

Budgeter
---------

Budgeters are Communards who are also responsible for analyzing and planning
spending.

.. uml::
    :includegraphics: scale=.55

    :Budgeter: as bud
    rectangle Reports {
        bud -- (View Profit & Loss)
        bud -- (View Events Overview)
    }

Budgeters may access the Profit & Loss for a specific date range in the
current year through the :ref:`Profit & Loss Reports <Profit and Loss Report
Page Design>`. They may reference the historical Balances for Asset, Liability
and Equity Accounts and the historical Profit & Loss amounts for Income and
Expense Accounts via the :ref:`Account History Page`.

Budgeters can view an overview of all Events via the :ref:`Event Reports Page
<Event Report Page Design>` which shows information such as each Event's location and Net
Profit.
