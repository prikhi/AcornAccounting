from django.conf.urls import patterns, url

urlpatterns = patterns(
    'events.views',

    (r'^search/$', 'quick_event_search'),

    url(r'^event/(?P<event_id>\d+)/$', 'show_event_detail',
        name='show_event_detail'),
)
