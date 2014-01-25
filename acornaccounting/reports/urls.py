from django.conf.urls import patterns

urlpatterns = patterns(
    'reports.views',

    (r'^events/$', 'events_report'),

)
