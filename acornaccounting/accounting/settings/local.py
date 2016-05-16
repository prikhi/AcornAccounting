from .base import *


DEBUG = True
TEMPLATE_DEBUG = DEBUG
COMPRESS_ENABLED = True
COMPRESS_DEBUG_TOGGLE = 'nocompress'

EMAIL_HOST = "localhost"
EMAIL_PORT = 1025

INTERNAL_IPS = ("127.0.0.1",)

INSTALLED_APPS += (
    'debug_toolbar',
    'django_extensions',
)

MIDDLEWARE_CLASSES += (
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'snippetscream.ProfileMiddleware',
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
