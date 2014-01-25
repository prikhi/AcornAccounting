from django.shortcuts import render

from events.models import Event


def events_report(request, template_name="reports/events.html"):
    """Display all :class:`Events<events.models.Event>`."""
    events = Event.objects.all()
    return render(request, template_name, {'events': events})
