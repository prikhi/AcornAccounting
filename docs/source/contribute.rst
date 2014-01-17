.. _Contributing:

.. _Development Standards:

=======================================
Development Standards and Contributing
=======================================

Bug Reports and Feature Requests
===================================

Bugs and New Features should be reported on either the internal Redmine bug
tracker or on the public Github Page.

All tickets should have descriptive titles.

Bugs should contain at least three sections: Steps to Reproduce, Results, and
Expected Results. Accurate and Concise reproduction steps reduces the amount
of time spent reproducing/debugging and increases the proportion of time spent
fixing the bug.

An example of an ideal bug report::

    Title: Account's Reconciled Balance Changes After Creating 2nd Fiscal Year

    Steps to Reproduce:
    1. Create Fiscal Year
    2. Reconcile Account w/ Statement in Current Fiscal Year
    3. Create New Fiscal Year
    4. Visit Reconcile Page for Account

    Result:
    Reconciled Balance is different from Statement Balance entered in step 2

    Expected Result:
    Reconciled Balance should be same as last reconciled Statement Balance

    Notes:
    Bug is caused by accounts/views.py#L289 on commit 1d7762a0

    Currently Sums all reconciled Transactions to get the reconciled balance.
    Instead, create a "Reconciled Balance" field on the Account model to store
    the Reconciled Balance after reconciling the Account.

Your bug report does not need to be anywhere close to this ideal, but the more
that you can incorporate, the faster a fix can be developed. The most important
parts to include are accurate and minimal steps to reproduce the bug and the
expected and actual results.

Features can have simple descriptions, but if Requests for Information from
developers are not replied to, then Feature Specifications will be determined
by the developer. To expedite development of a feature, it is recommended to
submit a :ref:`Specification <Specifications>` with the Ticket.

For example, an ideal feature request for a new Report would include:

* The name of the report
* How to reach the new report
* What the report should display(in all possible states)
* Optionally, how to calculate that information
* Any page interactions possible(changing the date range, sorting by column,
  etc.)
* Any new ways to exit the page(links or forms)
* Any behind the scenes changes(i.e. database changes)

A :ref:`Screen Description <Conditions Explanation>` and :term:`wireframe` will
be created by the requester and the task assignee.

Examples of complete specifications can be found in the :ref:`Design
Specifications`.


.. _Development Quickstart:

Development Quickstart
=======================

Brief guide to quickly getting up and running. A quick example:

First, start by cloning the source code repository:

.. code-block:: bash

    $ git clone git@aphrodite.acorn:~/Acorn-Accounting.git
    $ cd Acorn-Accounting

Create a new Python Virtual Environment:

.. code-block:: bash

    $ mkvirtualenv AcornAccounting -p python2

Install the development prerequisites:

.. code-block:: bash

    $ pip install -r requirements/local.txt

Setup the database and migrations, note that you must export a
``DJANGO_SETTINGS_MODULE`` or specify the settings module:

.. code-block:: bash

    $ cd Acorn-Accounting/
    $ ./manage.py syncdb --settings=accounting.settings.local
    $ ./manage.py migrate --settings=accounting.settings.local

Run the development server:

.. code-block:: bash

    $ ./manage.py runserver localhost:8000 --settings=accounting.settings.local

You should now have a working copy of the application on your workstation,
accessible at http://localhost:8000/.

To allow the application to be served to other computers, bind the server to all
available IP addresses instead of ``localhost``:

.. code-block:: bash

    $ ./manage.py runserver 0.0.0.0:8000 --settings=accounting.settings.local


Code Conventions
=================

The :pep:`8` is our baseline for coding style.

In short we use:

* 4 spaces per indentation
* 79 characters per line
* One import per line, grouped in the following order: standard library, 3rd
  party imports, local application imports
* One statement per line
* Docstrings for all public modules, functions, classes and methods.

The following naming conventions should be followed:

* Class names use CapitalWords
* Function names are lowercase, with words separated by underscores
* Use ``self`` and ``cls`` for first argument to instance and class methods,
  respectively.
* Non-public methods and variables should be prefixed with an underscore
* Constants in all uppercase.

Code should attempt to be idiomatic/pythonic, for example:

* Use list, dict and set comprehensions.
* Test existence in a sequence with ``in``.
* Use ``enumerate`` instead of loop counters.
* Use ``with ... as ...`` for context managers.
* Use ``is`` to compare against ``None`` instead of ``==``.
* Use parenthesis instead of backslashes for line continuations.

For more information and full coverage of conventions, please read :pep:`8`,
:pep:`257`, :pep:`20` and the `Django Coding Style Documentation`_.

There are tools available to help assess compliance to these conventions, such
as ``pep8`` and ``pylint``. Both of these tools are installed via ``pip``:

.. code-block:: bash

    $ pip install pep8
    $ pip install pylint

You may then run ``pep8`` on files to determine their compliance:

.. code-block:: bash

    $ pep8 accounts/signals.py
    accounts/signals.py:26:80: E501 line too long (116 > 79 characters)

Pylint may be used to show compliance to best practices and give your code a
generalized score. It is recommended to run pylint with some files and warnings
ignored, to reduce the amount of clutter and false positives:

.. code-block:: bash

    $ pylint --ignore=tests.py,migrations,wsgi.py,settings.py   \
        -d R0904,R0903,W0232,E1101,E1103,W0612,W0613,R0924

Version Control
================

AcornAccounting uses Git as a Version Control System.

Branches
---------

We have 2 long-term public branches:

* ``master`` - The latest stable release. This branch should be tagged with a
  new version number every time a branch is merged into it.
* ``develop`` - The release currently in development. New features and releases
  originate from this branch.

There are also multiple short-term supporting branches:

* ``hotfix`` - Used for immediate changes that need to be pushed out into
  production. These branches should originate from ``master`` and be merged
  into ``master`` and either the ``develop`` or current ``release`` if one
  exists.
* ``feature`` - Used for individual features and bug fixes, these branches are
  usually kept on local development machines. These should originate from and
  be merged back into ``develop``.
* ``release`` - Used for preparing the ``develop`` branch for merging into
  ``master``, creating a new release. These branches should originate from
  ``develop`` and be merged back into ``develop`` and ``master``. Releases
  should be created when all new features for a version are finished. Any new
  commits should only contain code refactoring and bug fixes.

This model is adapted from `A Successful Git Branching Model`_, however we use
a linear history instead of a branching history, so the ``--no-ff`` option
should be omitted during merges.

Commit Messages
----------------

Commit messages should follow the format described in `A Note About Git Commit
Messages`_. They should generally follow the following format::

    [TaskID#] Short 50 Char or Less Title

    Explanatory text or summary describing the feature or bugfix, capped
    at 72 characters per line, written in the imperative.

    Bullet points are also allowed:

    * Add method `foo` to `Bar` class
    * Modify `Base` class to be abstract
    * Remove `foobaz` method from `Bar` class
    * Refactor `bazfoo` function

    Refs/Closes/Fixes #TaskID: Task Name in Bug Tracker

For example::

    [#142] Add Account History

    * Add `HistoricalAccount` model to store archived Account information
    * Add `show_account_history` view to display Historical Accounts by
      month
    * Add Account History template and Sidebar link to Account History Page

    Closes #142: Add Historical Account Record

Workflow
---------

The general workflow we follow is based on `A Git Workflow for Agile Teams`_.
Work on a new task begins by branching from ``develop``. Feature branch names
should be in the format of ``tasknumber-short-title-or-name``. Commits on this
branch should be early and often. These commit messages are not permanent and
do not have to use the format specified above.

You should fetch and rebase against the upstream repository often in order to
prevent merging conflicts:

.. code-block:: bash

    $ git fetch origin develop
    $ git rebase origin/develop

When work is done on the task, you should rebase and squash your many commits
into a single commit:

.. code-block:: bash

    $ git rebase -i origin/develop

You may then choose which commits to reorder, squash or reword.

.. warning:: Only rebase commits that have not been published to public
    branches. Otherwise problems will arise in every other user's local
    repository. NEVER rewrite public branches and NEVER force a push unless
    you know EXACTLY what you are doing, and have preferably backed up the
    upstream repository.

Afterwards, merge your changes into ``develop`` and push your changes to the
upstream repository:

.. code-block:: bash

    $ git checkout develop
    $ git merge tasknumber-short-title-or-name
    $ git push origin develop

Preparing a Release
--------------------

Quick overview(will be expanded and solidified before v1.0.0 release):

#. Fork release off of the ``develop`` branch:

   .. code-block:: bash

       $ git checkout -b release-1.0.0 develop

#. Branch, Fix and Merge any bugs.
#. Bump version number and year in ``setup.py`` and ``docs/source/conf.py``.
#. Commit version changes.
#. Merge into master and push upstream:

   .. code-block:: bash

       $ git checkout master
       $ git merge release-1.2.0
       $ git tag -s -a v1.2.0
       $ git branch -d release-1.2.0
       $ git push origin master
       $ git push --tags origin master


Version Numbers
================

Each release will be tagged with a version number, using the MAJOR.MINOR.PATCH
`Semantic Versioning`_ format and specifications.

These version numbers indicate the changes to the public :term:`API`.

The PATCH number will be incremented if a new version contains only
backwards-compatible bug fixes.

The MINOR number is incremented for new, backwards-compatible functionality and
marking any new deprecations. Increasing the MINOR number should reset the
PATCH number to 0.

The MAJOR number is incremented if ANY backwards incompatible changes are
introduced to the public :term:`API`. Increasing the MAJOR number should reset
the MINOR and PATCH numbers to 0.

Pre-release versions may have additional data appended to the version, e.g.
``1.0.1-alpha`` or ``2.1.0-rc``.

The first stable release will begin at version 1.0.0, any versions before this
are for initial development and should be not be considered stable.

For more information, please review the `Semantic Versioning Specification`_.


Tests
=======

AcornAccounting is developed using Test-Driven Development, meaning tests are
written **before** any application code.

Features should be written incrementally alongside tests that define the
feature's requirements.

When fixing bugs, a test proving the bug's existence should first be written.
This test should fail initially and pass when the fix is implemented. This
ensures that the bug does not reappear in future versions.

All tests must pass before any branch is merged into the public branches
``master`` and ``develop``.

Our goal is to achieve 100% test coverage. Any code that does not have tests
written for it should be considered bugged.

Test coverage will be monitored, and no commits that reduce the Test Coverage
will be merged into the main branches. The `django-nose
<https://github.com/jbalogh/django-nose>`_ and `coverage
<https://pypi.python.org/pypi/coverage/3.5.2>`_ packages are recommended for
monitoring test coverage. These packages are included in the ``test``
requirements file, which can be installed by running:

.. code-block:: bash

    $ pip install -r requirements/test.txt

You can then check a branch's Test Coverage by running:

.. code-block:: bash

    $ manage.py test --settings=accounting.settings.test

or

.. code-block:: bash

    $ coverage -x manage.py test --settings=accounting.settings.test

If the code coverage is missing large chunks, try running the tests like this:

.. code-block:: bash

    $ coverage run manage.py test --settings=accounting.settings.test

To clear the coverage history, use the ``--cover-erase`` flag:

.. code-block:: bash

    $ manage.py test --settings=accounting.settings.test --cover-erase

You can generate an html report of the coverage by adding the ``--cover-html``
flag:

.. code-block:: bash

    $ manage.py test --settings=accounting.settings.test --cover-html

You can specify which package to test. Make sure to limit the coverage with
the ``--cover-package=`` flag:

.. code-block:: bash

    $ manage.py test accounts --settings=accounting.settings.test           \
        --cover-package=accounts

Or even exactly which test to run:

.. code-block:: bash

    $ manage.py test accounts.tests:BaseAccountModelTests.test_balance_flip \
        --settings=accounting.settings.test


Documentation
==============

Documentation for AcornAccounting is written in `reStructuredText`_  and
created using the `Sphinx`_ Documentation Generator. Sphinx's
``autodoc`` module is used to create the API specifications of the application
by scraping docstrings(:pep:`257`).

Each class, function, method and global should have an accurate docstring for
Sphinx to use.

Each feature or bug fix should include all applicable documentation changes such
as changes in :ref:`Screen Designs` or the :ref:`API <Technical
Specifications>`.

To build the Documentation, install the prerequisites then run the make command
to generate either html or pdf output:

.. code-block:: bash

    $ pip install -r requirements/local.txt
    $ cd docs/
    $ make html; make latexpdf

The output files will be located in the ``docs/build`` directory.


.. _Specifications:

Specifications
===============

Technical Specifications and Documentation should exist in the
docstrings(:pep:`257`) of the respective class, method, function, etc.

Design Specifications will be written for every usecase and screen in the
application. Wireframes will be created for each screen. And each screen's
Entry, Initial, Intermediate and Final Conditions should be clearly defined(see
:ref:`Conditions Explanation`).

For Usecases and Complex Screens, `UML`_ models such as Activity Diagrams will
be created using `plantUML`_ and `Sphinx`_.

Design Specifications written for new features should include all the
:ref:`Screen Conditions <Conditions Explanation>`.


.. _A Note About Git Commit Messages:
    http://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html

.. _A Successful Git Branching Model:
    http://nvie.com/posts/a-successful-git-branching-model/

.. _A Git Workflow for Agile Teams:
    http://reinh.com/blog/2009/03/02/a-git-workflow-for-agile-teams.html

.. _Django Coding Style Documentation:
    http://docs.djangoproject.com/en/1.4/internals/contributing/writing-code/coding-style/

.. _Java: https://www.java.com/en/

.. _Java Download:
    http://www.oracle.com/technetwork/java/javase/downloads/index.html

.. _plantUML:
    http://plantuml.sourceforge.net/index.html

.. _reStructuredText:
    http://docutils.sourceforge.net/docs/ref/rst/restructuredtext.html

.. _Semantic Versioning:
.. _Semantic Versioning Specification: http://semver.org/

.. _Sphinx: http://sphinx-doc.org/

.. _UML: http://en.wikipedia.org/wiki/Unified_Modeling_Language
