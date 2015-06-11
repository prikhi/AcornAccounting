from django.conf.urls import patterns, url

urlpatterns = patterns(
    'creditcards.views',
    url(r'^approve/$', 'list_creditcard_entries',
        name='list_creditcard_entries'),
    url(r'^add/$', 'add_creditcard_entry',
        name='add_creditcard_entry'),
    url(r'^view/(?P<entry_id>\d+)/$', 'show_creditcard_entry',
        name='show_creditcard_entry'),
    url(r'^edit/(?P<entry_id>\d+)/$', 'add_creditcard_entry',
        name='edit_creditcard_entry'),
)
