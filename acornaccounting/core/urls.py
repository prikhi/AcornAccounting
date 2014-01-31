from django.conf.urls import patterns, url

from .forms import BootstrapAuthenticationForm


urlpatterns = patterns(
    '',

    url(r'^$', 'accounts.views.show_accounts_chart', name='homepage'),
    url(r'^login/$', 'django.contrib.auth.views.login',
        {'template_name': 'login.html',
         'authentication_form': BootstrapAuthenticationForm},
        name='login'),
    url(r'^logout/$', 'django.contrib.auth.views.logout', {'next_page': '/'},
        name='logout'),
)
