=============================
Installation & Configuration
=============================

Downloading
============

Pip Install Directions

v1.0.0 should be hosted on `PyPi <https://pypi.python.org/pypi/>`_ so
installing is as easy as:

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
* ``local`` - development prerequisites such as the debug toolbar and
  documentation builders
* ``production`` - all packages required for real world usage

A set of dependencies may be installed via `pip`_:

.. code-block:: bash

    $ workon AcornAccounting
    $ pip install -r requirements/develop.txt


Configuration
==============

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

It is recommended to use `uWSGI`_ for serving the dynamic pages and either
`Apache`_ or `Nginx`_ for serving your static files.

Create and Initialize the Database
+++++++++++++++++++++++++++++++++++

You'll need a new Database and User, if you use PostgreSQL you may run:

.. code-block:: bash

    su - postgres
    createuser -DERPS accounting
    createdb accounting -O accounting

Set configuration values for the account you just created:

.. code-block:: bash

    export DJANGO_SETTINGS_MODULE=accounting.settings.production
    export DB_USER=accounting
    export DB_PASSWORD=<accounting user password>
    export DB_NAME=accounting

Then create the initial schema and migrate any database changes:

.. code-block:: bash

    cd acornaccounting
    python manage.py syncdb
    python manage.py migrate

Collect Static Files
+++++++++++++++++++++

Next collect all the static files into the directory you will serve them out
of:

.. code-block:: bash

    python manage.py collectstatic

Configure uWSGI
++++++++++++++++

You can use the following ini file to setup the uWSGI daemon:

.. code-block:: ini

    [uwsgi]
    uid = <your accounting user>
    gid = %(uid)
    chdir = <acornaccounting project root>

    plugin = python
    pythonpath = %(chdir)
    virtualenv = </path/to/virtualenv/>
    module = django.core.handlers.wsgi:WSGIHandler()

    socket = 127.0.0.1:3031
    master = true
    workers = 10
    max-requests = 5000
    vacuum = True

    daemonize = /var/log/accounting/uwsgi.log
    pidfile = /var/run/accounting.pid
    touch-reload = /tmp/accounting.touch

    env = DJANGO_SETTINGS_MODULE=accounting.settings.production
    env = DB_NAME=<database name
    env = DB_USER=<database user>
    env = DB_PASSWORD=<database password>
    env = DB_HOST=
    env = DB_PORT=
    env = DJANGO_SECRET_KEY=<your unique secret key>
    env = CACHE_LOCATION=127.0.0.1:11211

Make sure to review this and replace the necessary variables.

.. note::

    If you do not have a secure, unique secret key, you may generate one by
    running the following in the Python interpreter:

    .. code-block:: python

        import random
        print(''.join(
            [random.SystemRandom().choice(
                'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)')
             for i in range(50)])
        )

Depending on your OS, you may need to put this file in
``/etc/uwsgi/apps-available`` then link it to ``/etc/uwsgi/apps-enabled/``. Or
you may need to write an rc.d or init.d startup script:

.. code-block:: bash

    #!/bin/bash
    #
    # Start/Stop/Restart the Accounting uWSGI server
    #
    # To make the server start at boot make this file executable:
    #
    #       chmod 755 /etc/rc.d/rc.accounting

    INIFILE=/etc/uwsgi/accounting.ini
    PIDFILE=/var/run/accounting.pid

    case "$1" in
        'start')
            echo "Starting the Accounting uWSGI Process."
            uwsgi -i $INIFILE
            ;;
        'stop')
            echo "Stopping the Accounting uWSGI Process."
            uwsgi --stop $PIDFILE
            rm $PIDFILE
            ;;
        'restart')
            echo "Restarting the Accounting uWSGI Process."
            if [ -f $PIDFILE ]; then
                uwsgi --reload $PIDFILE
            else
                echo "Error: No Accounting uWSGI Process Found."
            fi
            ;;
        'status')
            if [ -f $PIDFILE ] && [ "$(ps -o comm= "$(cat $PIDFILE)")" = uwsgi ]; then
                echo "Accounting uWSGI Process is running."
            else
                echo "Accounting uWSGI Process is not running."
            fi
            ;;
        *)
            echo "Usage: /etc/rc.d/rc.accounting {start|stop|restart|status}"
            exit 1
            ;;
    esac

    exit 0


Apache VirtualHost
+++++++++++++++++++

The Virtual Host should redirect every request, except those to ``/static``, to
the uWSGI handler:

.. code-block:: bash

    <VirtualHost *:80>
        ServerName accounting.yourdomain.com
        DocumentRoot "/srv/accounting/"
        Alias /static /srv/accounting/static/
        <Directory "/srv/accounting/">
            Options Indexes FollowSymLinks MultiViews
            AllowOverride None
            Require all granted
        </Directory>
        <Location />
            Options FollowSymLinks Indexes
            SetHandler uwsgi-handler
            uWSGISocket 127.0.0.1:3031
        </Location>
        <Location /static>
            SetHandler none
        </Location>
        ErrorLog "/var/log/httpd/accounting-error_log"
        CustomLog "/var/log/httpd/accounting-access_log" common
    </VirtualHost>

Note that in the above setup, ``/srv/accounting/`` is linked to the Django
project's root directory ``acornaccounting``.

1-Step Deployment
++++++++++++++++++

1-step deploy script and indepth instuctions, with example apache and uwsgi
configs.

Look into `fabric <http://docs.fabfile.org/en/1.8/>`_ for automated deployment.
`Deploying Django with Fabric
<http://www.re-cycledair.com/deploying-django-with-fabric>`_

Ideally we would be able to run something like ``fab deploy_initial`` and ``fab
deploy``.

We can use fab templates, putting samples/templates in the ``/conf/``
directory.

v1.0.0 should include a 1-step build/deployment file.


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

.. _uWSGI: http://uwsgi-docs.readthedocs.org/en/latest/

.. _Apache: https://httpd.apache.org/

.. _Nginx: http://nginx.org/en/
