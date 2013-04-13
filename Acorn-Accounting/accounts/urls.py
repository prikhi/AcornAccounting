from django.conf.urls import patterns

urlpatterns = patterns('accounts.views',
    (r'^$', 'show_accounts_chart', {'template_name': 'accounts/account_charts.html'},
        'show_accounts_chart'),
    (r'^header/(?P<header_slug>[-\w]+)/$', 'show_accounts_chart'),
    (r'^account/(?P<account_slug>[-\w]+)/$', 'show_account_detail',
        {'template_name': 'accounts/account_detail.html'}, 'show_account_detail'),
    (r'^account/(?P<account_slug>[-\w]+)/reconcile/$', 'reconcile_account', {}, 'reconcile_account'),

    (r'^search/quick/account/$', 'quick_account_search'),
    (r'^search/quick/register/$', 'quick_bank_search'),
    (r'^search/quick/event/$', 'quick_event_search'),

    (r'^add/$', 'add_journal_entry',),
    (r'^add/(?P<journal_type>C[DR])/$', 'add_bank_entry'),
    (r'^add/transfer/$', 'add_transfer_entry'),

    (r'^edit/GJ/(?P<journal_id>\d+)/$', 'add_journal_entry',),
    (r'^edit/(?P<journal_type>C[DR])/(?P<journal_id>\d+)/$', 'add_bank_entry'),

    (r'^GJ/(?P<journal_id>\d+)/$', 'show_journal_entry',
        {'template_name': 'accounts/entry_detail.html'}, 'show_journal_entry'),
    (r'^(?P<journal_type>C[DR])/(?P<journal_id>\d+)/$', 'show_bank_entry'),

    (r'^event/(?P<event_id>\d+)/$', 'show_event_detail', {'template_name': 'accounts/event_detail.html'},
        'show_event_detail'),

    (r'^journal/$', 'journal_ledger', {'template_name': 'accounts/journal_ledger.html'}, 'journal_ledger'),
    (r'^register/(?P<account_slug>[-\w]+)/$', 'bank_register', {'template_name': 'accounts/bank_register.html'}, 'bank_register'),
)
