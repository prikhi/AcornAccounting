import os

from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured


def get_env_variable(var_name):
    """Get the environmental variable or raise an exception."""
    try:
        return os.environ.get(var_name)
    except KeyError:
        error_msg = "Set the {0} environmental variable.".format(var_name)
        raise ImproperlyConfigured(error_msg)


def project_root(path):
    """Return the absolute path to the path from the project root."""
    return os.path.abspath(os.path.join(
        os.path.dirname(__file__), os.pardir, os.pardir, path
    ))


DEFAULT_TAX_RATE = 5.3


SECRET_KEY = get_env_variable("DJANGO_SECRET_KEY")

STATIC_URL = '/static/'
STATIC_ROOT = 'static/'

MEDIA_URL = '/media/'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'


INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',

    'constance.backends.database',
    'constance',
    'localflavor',
    'mptt',
    'parsley',
    'south',
    'django_ajax',
    'compressor',

    'core',
    'accounts',
    'creditcards',
    'entries',
    'events',
    'fiscalyears',
    'receipts',
    'reports',
    'trips',
)


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': get_env_variable("DB_NAME"),
        'USER': get_env_variable("DB_USER"),
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
    }
}


# Cache Machine Settings
CACHES = {
    'default': {
        'BACKEND': 'caching.backends.memcached.MemcachedCache',
        'LOCATION': ['127.0.0.1:11211'],
    }
}

CACHE_MIDDLEWARE_SECONDS = 60 * 5
CACHE_MIDDLEWARE_KEY_PREFIX = ''


# Constance Settings
CONSTANCE_CONFIG = {
    'NAME': ('Acorn Accounting', "the name to use in titles and the navbar."),
    'COMPANY': ('Default Company', "your company's name."),
    'ADDRESS': ('123 ABC Lane', "your company's street address."),
    'CITY_STATE_ZIP': ('City, State Zipcode',
                       "your company's city, state and zipcode."),
    'PHONE': ('(456)555-0925', "your company's phone number."),
    'TAX_ID': ('00-0000000', "your company's federal tax id."),
}

CONSTANCE_BACKEND = 'constance.backends.database.DatabaseBackend'
CONSTANCE_DATABASE_CACHE_BACKEND = 'default'
CONSTANCE_DATABASE_PREFIX = 'constance:accounting:'


TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    "django.contrib.auth.context_processors.auth",
    "django.core.context_processors.debug",
    "django.core.context_processors.i18n",
    "django.core.context_processors.media",
    "django.core.context_processors.static",
    "django.core.context_processors.tz",
    "django.core.context_processors.request",
    "django.contrib.messages.context_processors.messages",
    "constance.context_processors.config",
    "accounts.context_processors.all_accounts",
)
TEMPLATE_DIRS = (project_root('templates'),)

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
)


MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.transaction.TransactionMiddleware',
)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        }
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
    }
}

ADMINS = (
    # ('Your Name', 'your_email@example.com'),
)

MANAGERS = ADMINS

MESSAGE_TAGS = {messages.ERROR: 'danger'}

SITE_ID = 1
TIME_ZONE = 'America/New_York'
LANGUAGE_CODE = 'en-us'
USE_I18N = True
USE_L10N = True
USE_TZ = True

ROOT_URLCONF = 'accounting.urls'
WSGI_APPLICATION = 'accounting.wsgi.application'
