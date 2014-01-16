from django.conf.urls import patterns, url

urlpatterns = patterns(
    'fiscalyears.views',

    (r'^add/$', 'add_fiscal_year'),
)
