from .base import *


SOUTH_TESTS_MIGRATE = False

INSTALLED_APPS += (
    'django_nose',
)

TEST_RUNNER = 'django_nose.NoseTestSuiteRunner'

NOSE_ARGS = [
    '--with-coverage',
    '--cover-branches',
    '--with-progressive',
    '--ignore-files="migrations"',
    ('--cover-package=accounts,core,creditcards,entries,events,fiscalyears,'
     'receipts,reports')
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'memory://testdb',
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}
