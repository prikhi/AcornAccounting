from django.conf.urls import patterns

urlpatterns = patterns(
    'entries.views',

    (r'^add/$', 'add_journal_entry',),
    (r'^add/(?P<journal_type>C[DR])/$', 'add_bank_entry'),
    (r'^add/transfer/$', 'add_transfer_entry'),

    (r'^edit/GJ/(?P<entry_id>\d+)/$', 'add_journal_entry',),
    (r'^edit/(?P<journal_type>C[DR])/(?P<entry_id>\d+)/$', 'add_bank_entry'),

    (r'^GJ/(?P<entry_id>\d+)/$', 'show_journal_entry'),
    (r'^(?P<journal_type>C[DR])/(?P<entry_id>\d+)/$', 'show_bank_entry'),

    (r'^journal/$', 'journal_ledger'),
)
