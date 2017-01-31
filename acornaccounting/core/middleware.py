import re

from django.http import HttpResponseRedirect
from django.conf import settings


EXEMPT_URLS = [re.compile(settings.LOGIN_URL.lstrip('/'))]
if hasattr(settings, 'REQUIRE_LOGIN_EXEMPT_URLS'):
    EXEMPT_URLS += [compile(expr) for expr in settings.LOGIN_EXEMPT_URLS]


class LoginRequiredMiddleware(object):
    """Add Ability to Hide All Pages From Unauthorized Users.

    Checks the ``REQUIRE_LOGIN`` setting to see if the Middleware is
    enabled, and adds exceptions for any URL regexes defined in the
    ``REQUIRE_LOGIN_EXEMPT_URLS`` setting.

    """

    def process_request(self, request):
        """Redirect to Login Page if Enabled & User Unauthenticated."""
        if settings.REQUIRE_LOGIN and not request.user.is_authenticated():
            path = request.path_info.lstrip('/')
            if not any(m.match(path) for m in EXEMPT_URLS):
                return HttpResponseRedirect(
                    "{}?next={}".format(settings.LOGIN_URL, request.path))
