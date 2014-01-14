from django.conf.urls import patterns

urlpatterns = patterns(
    'accounts.views',

    (r'^$', 'show_accounts_chart', {
        'template_name': 'accounts/account_charts.html'},
        'show_accounts_chart'),

    (r'^header/(?P<header_slug>[-\w]+)/$', 'show_accounts_chart'),

    (r'^account/(?P<account_slug>[-\w]+)/$', 'show_account_detail', {
        'template_name': 'accounts/account_detail.html'},
     'show_account_detail'),
    (r'^account/(?P<account_slug>[-\w]+)/reconcile/$', 'reconcile_account', {},
     'reconcile_account'),

    (r'^history/$', 'show_account_history'),
    (r'^history/(?P<year>\d{2}(?:\d{2})?)/(?P<month>\d(?:\d)?)/',
     'show_account_history'),

    (r'^search/quick/account/$', 'quick_account_search'),
    (r'^search/quick/bank-journal/$', 'quick_bank_search'),
    (r'^search/quick/event/$', 'quick_event_search'),

    (r'^add/$', 'add_journal_entry',),
    (r'^add/(?P<journal_type>C[DR])/$', 'add_bank_entry'),
    (r'^add/transfer/$', 'add_transfer_entry'),
    (r'^add/fiscal_year/$', 'add_fiscal_year'),

    (r'^edit/GJ/(?P<entry_id>\d+)/$', 'add_journal_entry',),
    (r'^edit/(?P<journal_type>C[DR])/(?P<entry_id>\d+)/$', 'add_bank_entry'),

    (r'^GJ/(?P<entry_id>\d+)/$', 'show_journal_entry',
        {'template_name': 'accounts/entry_detail.html'}, 'show_journal_entry'),
    (r'^(?P<journal_type>C[DR])/(?P<entry_id>\d+)/$', 'show_bank_entry'),

    (r'^event/(?P<event_id>\d+)/$', 'show_event_detail',
     {'template_name': 'accounts/event_detail.html'}, 'show_event_detail'),

    (r'^journal/$', 'journal_ledger',
     {'template_name': 'accounts/journal_ledger.html'}, 'journal_ledger'),
    (r'^bank-journal/(?P<account_slug>[-\w]+)/$', 'bank_journal',
     {'template_name': 'accounts/bank_journal.html'}, 'bank_journal'),
)
