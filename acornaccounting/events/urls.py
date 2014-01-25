from django.conf.urls import patterns, url

urlpatterns = patterns(
    'events.views',

    url(r'^event/(?P<event_id>\d+)/$', 'show_event_detail',
        name='show_event_detail'),
)
