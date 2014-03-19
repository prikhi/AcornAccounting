from dateutil.relativedelta import relativedelta

from .models import FiscalYear


def get_start_of_current_fiscal_year():
    """
    Determine the Start Date of the Latest :class:`~.models.FiscalYear`.

    If there are no :class:`FiscalYears<.models.FiscalYear>` then this
    method will return ``None``.

    If there is one :class:`~.models.FiscalYear` then the starting date
    will be the :attr:`~.models.FiscalYear.period` amount of months before
    it's :attr:`~.models.FiscalYear.date`.

    If there are multiple :class:`FiscalYears<.models.FiscalYear>` then the
    first day and month after the Second Latest :class:`~.models.FiscalYear`
    will be returned.

    :returns: The starting date of the current :class:`~.models.FiscalYear`.
    :rtype: :class:`datetime.date` or :obj:`None`

    """
    if FiscalYear.objects.exists():
        if FiscalYear.objects.count() > 1:
            second_latest = FiscalYear.objects.order_by('-date')[1]
            return second_latest.date + relativedelta(months=1)
        else:
            current_year = FiscalYear.objects.get()
            months_to_fiscal_start = current_year.period - 1
            return (current_year.date -
                    relativedelta(months=months_to_fiscal_start))
    else:
        return None
