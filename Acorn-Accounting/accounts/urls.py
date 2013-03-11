from django.conf.urls import patterns, url
from django.views.generic import TemplateView

urlpatterns = patterns('accounts.views',
    (r'^$', 'show_accounts_chart', {'template_name': 'accounts/account_charts.html'},
        'show_accounts_chart'),
    (r'^header/(?P<header_slug>[-\w]+)/$', 'show_accounts_chart'),

    (r'^detail/(?P<account_slug>[-\w]+)/$', 'show_account_detail',
        {'template_name': 'accounts/account_detail.html'}, 'show_account_detail'),

    (r'^search/quick/account/$', 'quick_account_search'),

    url(r'^entry/$', TemplateView.as_view(template_name="accounts/entry_index.html"), name='entry_main'),
    (r'^entry/add/(?P<journal_type>\w{2})/$', 'add_journal_entry',),
    (r'^entry/add/bank/(?P<journal_type>\w{2})/$', 'add_bank_entry'),
    (r'^entry/add/transfer/$', 'add_transfer_entry'),
    (r'^entry/edit/(?P<journal_type>\w{2})/(?P<journal_id>\d+)/$', 'add_journal_entry',),

    (r'^entry/(?P<journal_type>\w{2})/(?P<journal_id>\d+)/$', 'show_journal_entry',
        {'template_name': 'accounts/entry_detail.html'}, 'show_journal_entry'),

    (r'^journal/$', 'journal_ledger',
        {'template_name': 'accounts/journal_ledger.html'}, 'journal_ledger'),
)
