=================
Acorn Accounting
=================

Acorn Accounting is an Open Source Double Entry Accounting System written using
Python and Django.

Acorn Accounting is targeted towards egalitarian communities with needs such
as paying stipends, entering town trips and tracking membership.


Quickstart
===========

Install virtualenv::

    $ pip install virtualenv virtualenvwrapper

Configure virtualenvwrapper::

    $ export WORKON_HOME=~/.virtualenvs
    $ mkdir -p $WORKON_HOME
    $ source /usr/bin/virtualenvwrapper.sh      # Or add this to your .bashrc

Create a new virtual environment::

    $ mkvirtualenv AcornAccounting
    $ workon AcornAccounting

Install the prerequisites::

    $ pip install -r requirements/base.txt

Specify some environmental variables::

    $ export DJANGO_SECRET_KEY="A Random 50 Character String"
    $ export DB_NAME="<database name>"
    $ export DB_USER="<database username>"

Create all necessary tables::

    $ python manage.py syncdb --settings=accounting.settings.base
    $ python manage.py migrate --settings=accounting.settings.base

Run the development server::

    $ cd acornaccounting
    $ python manage.py runserver --settings=accounting.settings.base

You can omit the ``settings`` flag by setting the ``DJANGO_SETTINGS_MODULE``
environmental variable::

    $ export DJANGO_SETTINGS_MODULE=accounting.settings.base
    $ python manage.py runserver


Running Tests
==============

Install the prerequisites::

    $ pip install -r requirements/test.txt

Run the tests::

    $ cd acornaccounting
    $ py.test

To continuously run tests when source files change::

    $ ptw


Building the Full Documentation
================================

Install the prerequisites::

    $ pip install -r requirements/local.txt

Build the documentation::

    $ cd docs
    $ make html

The HTML files will be output to the ``docs/build/html`` directory.
