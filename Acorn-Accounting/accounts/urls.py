from django.conf.urls import patterns, url

urlpatterns = patterns(
    'accounts.views',

    (r'^$', 'show_accounts_chart'),

    (r'^header/(?P<header_slug>[-\w]+)/$', 'show_accounts_chart'),

    url(r'^account/(?P<account_slug>[-\w]+)/$', 'show_account_detail',
        name='show_account_detail'),
    (r'^account/(?P<account_slug>[-\w]+)/reconcile/$', 'reconcile_account'),

    (r'^history/$', 'show_account_history'),
    (r'^history/(?P<year>\d{2}(?:\d{2})?)/(?P<month>\d(?:\d)?)/',
     'show_account_history'),

    (r'^search/quick/account/$', 'quick_account_search'),
    (r'^search/quick/bank-journal/$', 'quick_bank_search'),

    url(r'^bank-journal/(?P<account_slug>[-\w]+)/$', 'bank_journal',
        name='bank_journal'),
)
