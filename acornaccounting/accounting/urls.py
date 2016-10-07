from django.conf import settings
from django.conf.urls import patterns, include, url
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

admin.autodiscover()

urlpatterns = patterns(
    '',

    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^admin/', include(admin.site.urls)),

    url(r'^', include('core.urls')),
    url(r'^accounts/', include('accounts.urls')),
    url(r'^creditcards/', include('creditcards.urls')),
    url(r'^entries/', include('entries.urls')),
    url(r'^events/', include('events.urls')),
    url(r'^fiscal-years/', include('fiscalyears.urls')),
    url(r'^reports/', include('reports.urls')),
    url(r'^trips/', include('trips.urls')),
    url(r'^bank/import/', include('bank_import.urls')),
) + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += staticfiles_urlpatterns()
