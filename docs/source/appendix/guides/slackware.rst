================
Slackware Linux
================

This section will guide you through installation and deployment on Slackware
Linux. Slackware 14.0 was used, but it should be fairly portable between
versions if you use your versions SlackBuilds.

User
-----

Start off by creating a new user to store and serve the application:

.. code-block:: bash

    useradd -m -s /bin/bash accounting
    passwd accounting


Dependencies
-------------

Make sure your system is updated and install some basic dependencies from the
Slackware repositories. Additional dependencies may be discovered when trying
to build PostgreSQL and Memcached.

.. code-block:: bash

    slackpkg update
    slackpkg upgrade-all
    slackpkg install libmpc mpfr readline zlib libxml2 libxslt openldap-client tcl httpd git

Mark ``/etc/rc.d/rc.httpd`` as executable so it will start at boot:

.. code-block:: bash

    chmod a+x /etc/rc.d/rc.httpd


We can then proceed to installing the PostgreSQL database, uWSGI and Memcached
via `SlackBuilds`_.

PostgreSQL
+++++++++++

First we must create a postgres user and group. ID 209 is used to avoid
conflicts with other SlackBuilds:

.. code-block:: bash

    groupadd -g 209 postgres
    usereadd -u 209 -g 209 -d /var/lib/pgsql postgres

We can then download and extract the SlackBuild:

.. code-block:: bash

    wget http://slackbuilds.org/slackbuilds/14.0/system/postgresql.tar.gz
    tar xvfz postgresql.tar.gz

We need to manually download the source code to the extracted directory, then
we can compile it into a package:

.. code-block:: bash

    cd postgresql
    wget ftp://ftp.postgresql.org/pub/source/v9.3.0/postgresql-9.3.0.tar.bz2
    ./postgresql.SlackBuild

Now we can install the new package:

.. code-block:: bash

    installpkg /tmp/postgresql-*.tgz

The database files need to be initialized:

.. code-block:: bash

    su postgres -c "initdb -D /var/lib/pgsql/9.3/data"

We should make the rc.d script executable and fire up PostgreSQL:

.. code-block:: bash

    chmod a+x /etc/rc.d/rc.postgresql
    /etc/rc.d/rc.postgresql start

We will then edit ``/etc/rc.d/rc.local`` and ``/etc/rc.d/rc.local_shutdown``,
making sure it is started at boot and shutdown cleanly.

.. code-block:: bash

    # rc.local
    # Startup postgresql
    if [ -x /etc/rc.d/rc.postgresql ]; then
        /etc/rc.d/rc.postgresql start
    fi

.. code-block:: bash

    # rc.local_shutdown
    #!/bin/sh
    # Stop postgres
    if [ -x /etc/rc.d/rc.postgresql ]; then
        /etc/rc.d/rc.postgresql stop
    fi


Memcached
++++++++++

Memcached requires you to build the ``libevent`` and ``libmemcached``
`SlackBuilds`_ first:

.. code-block:: bash

    wget http://slackbuilds.org/slackbuilds/14.0/libraries/libevent.tar.gz
    tar xvfz libevent.tar.gz
    cd libevent
    wget https://github.com/downloads/libevent/libevent/libevent-2.0.21-stable.tar.gz
    ./libevent.SlackBuild
    installpkg /tmp/libevent-*.tgz

    cd ..
    wget http://slackbuilds.org/slackbuilds/14.0/libraries/libmemcached.tar.gz
    tar xvfz libmemcached.tar.gz
    cd libmemcached
    wget https://launchpad.net/libmemcached/1.0/1.0.15/+download/libmemcached-1.0.15.tar.gz
    ./libmemcached.SlackBuild
    installpkg /tmp/libmemcached-*.tgz

You can build and install Memcached the same way:

.. code-block:: bash

    cd ..
    wget http://slackbuilds.org/slackbuilds/14.0/network/memcached.tar.gz
    tar xvfz memcached.tar.gz
    cd memcached
    wget http://memcached.googlecode.com/files/memcached-1.4.15.tar.gz
    ./memcached.SlackBuild
    installpkg /tmp/memcached-*.tgz

Add the following line to ``/etc/rc.d/rc.local`` in order to get Memcached to
start at boot:

.. code-block:: bash

    # /etc/rc.d/rc.local
    memcached -d 127.0.0.1 -u accounting

Keep in mind the default port is ``11211``.

uWSGI
++++++

Again, download the SlackBuild and source, compile and install the package:

.. code-block:: bash

    cd ..
    wget http://slackbuilds.org/slackbuilds/14.1/network/uwsgi.tar.gz
    tar xvfz uwsgi.tar.gz
    cd uwsgi
    wget http://projects.unbit.it/downloads/uwsgi-1.9.6.tar.gz
    ./uwsgi.SlackBuild
    installpkg /tmp/uwsgi-1.9.6-x86_64-1_SBo.tgz

We will also need to build the Apache module:

.. code-block:: bash

    cd /tmp/SBo/uwsgi-1.9.6/apache2
    sudo apxs -i -c mod_uwsgi.c

Edit ``/etc/httpd/httpd.conf`` to use the uWSGI module::

    echo "LoadModule uwsgi_module lib64/httpd/modules/mod_uwsgi.so" >> /etc/httpd/httpd.conf

Pip and VirtualEnv
+++++++++++++++++++

We will use pip and virtualenv to manage the python dependencies. Start off by
downloading and running the pip install script:

.. code-block:: bash

    wget https://raw.github.com/pypa/pip/master/contrib/get-pip.py
    python get-pip.py

Then install virtualenv:

.. code-block:: bash

    pip install virtualenv


Install the Accounting Application
-----------------------------------

Download Source Code
+++++++++++++++++++++

We are now ready to grab the source code from the git repository. Do this as
the ``accounting`` user. We chose to store the local repository at
``~/AcornAccounting/``:

.. code-block:: bash

    su - accounting
    git clone ssh://git@aphrodite.acorn:22/srv/git/AcornAccounting.git ~/AcornAccounting

Create a Virtual Environment
++++++++++++++++++++++++++++

Before proceeding we should make a VirtualEnv for the ``accounting`` user:

.. code-block:: bash

    virtualenv ~/AccountingEnv

Activate the VirtualEnv by sourcing the ``activate`` script:

.. code-block:: bash

    source ~/AccountingEnv/bin/activate

Install Python Dependencies
++++++++++++++++++++++++++++

We can now install the python dependencies into our VirtualEnv:

.. code-block:: bash

    cd AcornAccounting
    pip install -r requirements/production.txt

Create a PostgreSQL User and Database
++++++++++++++++++++++++++++++++++++++

We need a database to store our data, and a user that is allowed to access it,
we decided to name both ``accounting``:

.. code-block:: bash

    su - postgres
    createuser -DERPS accounting
    createdb accounting -O accounting
    exit

You can now sync and migrate the database, creating the necessary schema:

.. code-block:: bash

    # Fill in the following variables according to your setup
    export DJANGO_SETTINGS_MODULE=accounting.settings.production
    export DJANGO_SECRET_KEY=<your unique secret key>
    export DB_HOST=localhost
    export DB_USER=accounting
    export DB_PASSWORD=<accounting user password>
    export DB_NAME=accounting

    cd ~/AcornAccounting/acornaccounting
    python manage.py syncdb
    python manage.py migrate

.. note::

    If you already have a database dump in a ``.sql`` file, you may restore
    this into your new database by running the following:

    .. code-block:: bash

        psql -U accounting -d accounting -f database_dump.sql

You can test your installation by running the following, assuming you have set
the environmental variables from above:

.. code-block:: bash

    python manage.py runserver 0.0.0.0:8000


Deployment
-----------

Now that the application is installed and running, we will serve the files and
pages using uWSGI and Apache. Apache will only be serving our static files.

The application will be served out of ``/srv/accounting``, which should be a
link to ``/home/accounting/AcornAccounting/acornaccounting/``:

.. code-block:: bash

    ln -s /home/accounting/AcornAccounting/acornaccounting/ /srv/accounting

Configure uWSGI
++++++++++++++++

We will need two things to use uWSGI: a configuration file and an rc.d script
for starting and stopping the uWSGI daemon.

We should start by creating a directory for our configuration file(you no
longer need to be the ``accounting`` user):

.. code-block:: bash

    mkdir /etc/uwsgi

Create the ``/etc/uwsgi/accounting.ini`` file containing the following
configuration:

.. code-block:: ini

    [uwsgi]
    uid = accounting
    gid = %(uid)
    chdir = /srv/accounting/

    plugin = python
    pythonpath = %(chdir)
    virtualenv = /home/accounting/AccountingEnv/
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
    env = DB_NAME=accounting
    env = DB_PASSWORD=
    env = DB_USER=accounting
    env = DB_HOST=
    env = DB_PORT=
    env = DJANGO_SECRET_KEY=
    env = CACHE_LOCATION=127.0.0.1:11211

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

We'll need to make some of the folders specified in the config:

.. code-block:: bash

    mkdir /var/log/accounting
    chown accounting /var/log/accounting
    mkdir /var/run/uwsgi

Now we can make an rc.d script at ``/etc/rc.d/rc.accounting`` to let us start
and stop the server:

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
        *)
            echo "Usage: /etc/rc.d/rc.accounting {start|stop|restart}"
            exit 1
            ;;
    esac

    exit 0

We need to give this the correct permissions to enable it:

.. code-block:: bash

    chmod 755 /etc/rc.d/rc.accounting
    /etc/rc.d/rc.accounting start

Make sure this has started the application and spawned uWSGI workers by
checking the log:

.. code-block:: bash

    less /var/log/accounting/uwsgi.log


We can automatically start the process from ``rc.local`` and stop it from
``rc.local_shutdown``:

.. code-block:: bash

    # /etc/rc.d/rc.local
    if [ -x /etc/rc.d/rc.accounting ]; then
        /etc/rc.d/rc.accounting start
    fi

.. code-block:: bash

    # /etc/rc.d/rc.local_shutdown
    if [ -x /etc/rc.d/rc.accounting ]; then
        /etc/rc.d/rc.accounting stop
    fi

Configuring Apache
+++++++++++++++++++

Apache will serve any files under the ``/static/`` directory, passing all other
requests to uWSGI.

First we should collect all the static files into the appropriate directory:

.. code-block:: bash

    su - accounting
    source AccountingEnv/bin/activate
    cd AcornAccounting/acornaccounting
    python manage.py collectstatic


Now we can create a virtual host in ``/etc/httpd/extra/httpd-accounting.conf``
to hold the configuration:

.. code-block:: bash

    <VirtualHost *:80>
        ServerName accounting.yourdomain.com
        ErrorLog "/var/log/httpd/accounting-error_log"
        CustomLog "/var/log/httpd/accounting-access_log" common
        DocumentRoot "/srv/accounting/"
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

        Alias /static /srv/accounting/static/
        <Location /static>
            SetHandler none
        </Location>

        Alias /media/uploads /srv/accounting/uploads/
        <Location /media/uploads>
            SetHandler none
        </Location>
    </VirtualHost>

Include this configuration file in ``/etc/httpd/httpd.conf``:

.. code-block:: bash

    echo "Include /etc/httpd/extra/httpd-accounting.conf" >> /etc/httpd/httpd.conf

Then restart apache:

.. code-block:: bash

    /etc/rc.d/rc.httpd restart


The application should now be accessible at
``http://accounting.yourdomain.com``

You can restart the uWSGI server by touching ``/tmp/accounting.touch``:

.. code-block:: bash

    touch /tmp/accounting.touch


.. _SlackBuilds: http://slackbuilds.org/
