from django.conf.urls import patterns

urlpatterns = patterns(
    'reports.views',

    (r'^events/$', 'events_report'),
    (r'^profit-loss/$', 'profit_loss_report'),
    (r'^trial-balance/$', 'trial_balance_report'),

)
