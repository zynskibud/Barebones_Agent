from datetime import date

from billing import add_months, billing_dates, days_until_billing, next_billing_date


def test_add_months_mid_month():
    assert add_months(date(2024, 1, 15), 1) == date(2024, 2, 15)


def test_add_months_crosses_the_year():
    assert add_months(date(2024, 11, 10), 3) == date(2025, 2, 10)


def test_next_billing_date_skips_past_dates():
    assert next_billing_date(date(2024, 1, 5), date(2024, 3, 6)) == date(2024, 4, 5)


def test_billing_dates_lists_each_month():
    assert billing_dates(date(2024, 1, 5), 3) == [
        date(2024, 1, 5),
        date(2024, 2, 5),
        date(2024, 3, 5),
    ]


def test_days_until_billing():
    assert days_until_billing(date(2024, 1, 5), date(2024, 1, 1)) == 4
