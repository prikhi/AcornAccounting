=============================
Installation & Configuration
=============================

Downloading
============

IN PROGRESS

Pip Install Directions

v1.0.0 should be hosted on `PyPi <https://pypi.python.org/pypi/>`_ so installing is as easy as:

.. code-block:: bash

    $ pip install acornaccounting

See `The Hitchhiker's Guide to Packaging
<http://guide.python-distribute.org/>`_ for information on how to get that set
up.

Git Clone Directions

Developers will want to clone the current source code repository:

.. code-block:: bash

    $ git clone git@aphrodite.acorn:~/Acorn-Accounting.git/

The current public release is located on the ``master`` branch while new
development occurs on the ``develop`` branch.

See :ref:`Contributing` for more information.

Install Prerequisites
======================

You should install `python 2`_ and `pip`_ via your package manager.

On Arch Linux:

.. code-block:: bash

    $ sudo pacman -S python2 python2-pip

On Slackware:

.. code-block:: bash

    $ sudo /usr/sbin/slackpkg install python
    $ wget https://raw.github.com/pypa/pip/master/contrib/get-pip.py
    $ sudo python get-pip.py

On Debian/Ubuntu:

.. code-block:: bash

    $ sudo apt-get install python-pip

Optionally you may want to install `virtualenv`_ and `virtualenvwrapper`_ to
manage and isolate the python dependencies.

.. code-block:: bash

    $ sudo pip install virtualenv virtualenvwrapper

Make sure to do the initial setup for `virtualenv`_:

.. code-block:: bash

    $ export WORKON_HOME=~/.virtualenv/
    $ mkdir -p $WORKON_HOME
    $ source virtualenvwrapper.sh

Then you may create an environment for AcornAccounting:

.. code-block:: bash

    $ mkvirtualenv AcornAccounting

You may then install dependencies into this virtual environment. There are
multiple tiers of dependencies:

* ``base`` - minimum requirements needed to run the application
* ``test`` - requirements necessary for running the test suite
* ``local`` - development prerequisites such as the the debug toolbar and
    documentation builders
* ``production`` - all packages required for real world usage

A set of dependencies may be installed via `pip`_:

.. code-block:: bash

    $ workon AcornAccounting
    $ pip install -r requirements/develop.txt


Configuration
==============

IN PROGRESS

Talk about setting up settings like Company Name, Address, Daily Payment
Amount, etc.

Also talk about how to specify settings in Environmental Variables instead of
in files, especially for things like ``DJANGO_SECRET_KEY``.

Some settings are set through environmental variables instead of files. These
include settings with sensitive information, and allows us to keep the
information out of version control.

You may set these variables directly in the terminal or add them to your
virtualenv's ``activate`` script::

    $ DB_USER='prikhi' DB_NAME='DjangoAccounting' ./manage.py runserver
    $ export DB_NAME='DjangoAccounting'
    $ ./manage.py runserver

The required environmental variables are ``DJANGO_SECRET_KEY``, ``DB_NAME`` and
``DB_USER``.


Deployment
===========

IN PROGRESS

1-step deploy script or indepth instuctions, with example apache config.

Talk about mod_python, apache + virtualenv

Look into `gunicorn <http://gunicorn.org/>`_, `uwsgi
<https://github.com/unbit/uwsgi>`_ and `fabric
<http://docs.fabfile.org/en/1.8/>`_ for automated deployment and serving.

v1.0.0 should include a 1-step build/deployment file.

This is still stuff I have to figure out.

`Deploying Django with Fabric
<http://www.re-cycledair.com/deploying-django-with-fabric>`_

Must exist before release of v1.0.0


Building the Documentation
===========================

`pip`_ may be used to install most prerequisites required:

.. code-block:: bash

    $ pip install -r requirements/local.txt

`Java`_ is optional, but required to create the plantUML images. You can
install it via your package manager.

On Arch Linux:

.. code-block:: bash

    $ sudo pacman -S jre7-openjdk

On Debian:

.. code-block:: bash

    $ sudo apt-get install default-jdk

On Slackware you must manually download the source from Oracle, `available here
<http://www.oracle.com/technetwork/java/javase/downloads/index.html>`_. You may
then use the slackbuild at
http://slackbuilds.org/repository/14.1/development/jdk/ to install the package:

.. code-block:: bash

    $ wget http://slackbuilds.org/slackbuilds/14.0/development/jdk.tar.gz
    $ tar xfz jdk.tar.gz
    $ cd jdk
    $ mv ~/jdk-7*-linux-*.tar.gz .
    $ ./jdk.SlackBuild
    $ sudo installpkg /tmp/jdk-7u45-x86_64-1_SBo.tgz
    # Add java to your $PATH:
    $ sudo ln -s /usr/lib64/java/jre/bin/java /usr/bin/java


You can now build the full documentation in HTML or PDF format:

.. code-block:: bash

    $ cd docs/
    $ make html
    $ make latexpdf

The output files will be located in ``docs/build/html`` and
``docs/build/latex``.


.. _Java: http://www.java.com/en/

.. _pip: http://www.pip-installer.org/en/latest/

.. _python 2: http://www.python.org/

.. _virtualenv: https://github.com/pypa/virtualenv

.. _virtualenvwrapper: https://github.com/bernardofire/virtualenvwrapper
