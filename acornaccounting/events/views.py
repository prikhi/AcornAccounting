from django.shortcuts import render, get_object_or_404

from .models import Event


def show_event_detail(request, event_id,
                      template_name="events/event_detail.html"):
    """Shows the details of an :class:`~events.models.Event` instance.

    :param event_id: The id of the :class:`~events.models.Event` to show.
    :type event_id: int
    :param template_name: The template to use.
    :type template_name: string
    :returns: HTTP Response containing the :class:`~events.models.Event`
            instance, and the :class:`Event's<events.models.Event>` Debit
            Total, Credit Total and Net Change.
    :rtype: HttpResponse
    """
    event = get_object_or_404(Event, id=event_id)
    debit_total, credit_total, net_change = event.transaction_set.get_totals(
        net_change=True)
    return render(request, template_name, locals())
