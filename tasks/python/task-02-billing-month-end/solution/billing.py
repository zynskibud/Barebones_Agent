"""Billing dates for monthly subscriptions."""

import calendar
from datetime import date


def add_months(start, months):
    """Return the date `months` after `start`.

    The day stays the same when it exists. Otherwise it is the last day
    of the target month.
    """
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(start.day, last_day)
    return date(year, month, day)


def next_billing_date(start, today):
    """Return the first billing date that is on or after `today`."""
    billing = start
    months = 0
    while billing < today:
        months += 1
        billing = add_months(start, months)
    return billing


def billing_dates(start, count):
    """Return the first `count` billing dates, starting with `start`."""
    return [add_months(start, i) for i in range(count)]


def days_until_billing(start, today):
    """Return how many days remain until the next billing date."""
    return (next_billing_date(start, today) - today).days
