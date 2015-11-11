from django.conf.urls import patterns, url

urlpatterns = patterns(
    'trips.views',
    url(r'^approve/$', 'list_trip_entries', name='list_trip_entries'),
    url(r'^add/$', 'add_trip_entry', name='add_trip_entry'),
    url(r'^view/(?P<entry_id>\d+)/$', 'show_trip_entry',
        name='show_trip_entry'),
    url(r'^edit/(?P<entry_id>\d+)/$', 'add_trip_entry',
        name='edit_trip_entry'),
)
