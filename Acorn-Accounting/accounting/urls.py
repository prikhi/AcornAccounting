from django.conf.urls import patterns, include, url

from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

admin.autodiscover()

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'accounting.views.home', name='home'),
    # url(r'^accounting/', include('accounting.foo.urls')),

    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^accounts/', include('accounts.urls')),
)

urlpatterns += staticfiles_urlpatterns()
