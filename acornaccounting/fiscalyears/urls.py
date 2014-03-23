from django.conf.urls import patterns

urlpatterns = patterns(
    'fiscalyears.views',

    (r'^$', 'add_fiscal_year'),
)
