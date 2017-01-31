from django.conf import settings


def template_accessible_settings(request):
    """Inject template-accessible settings into every context."""
    return {
        'settings': {'REQUIRE_LOGIN': settings.REQUIRE_LOGIN}
    }
