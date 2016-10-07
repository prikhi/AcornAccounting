"""Route the Bank Statement Import Views."""
from django.conf.urls import patterns, url

urlpatterns = patterns(
    'bank_import.views',
    url(r'^$', 'import_bank_statement', name='import_bank_statement'),
)
