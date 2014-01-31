from django.conf.urls import patterns, include, url

from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

admin.autodiscover()

urlpatterns = patterns(
    '',

    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^admin/', include(admin.site.urls)),

    url(r'^', include('core.urls')),
    url(r'^accounts/', include('accounts.urls')),
    url(r'^entries/', include('entries.urls')),
    url(r'^events/', include('events.urls')),
    url(r'^fiscalyears/', include('fiscalyears.urls')),
    url(r'^reports/', include('reports.urls')),
)

urlpatterns += staticfiles_urlpatterns()
