from datetime import date

from billing import add_months, billing_dates, days_until_billing, next_billing_date


def test_mid_month_is_unchanged():
    assert add_months(date(2024, 1, 15), 1) == date(2024, 2, 15)


def test_jan_31_to_feb_in_a_leap_year():
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)


def test_jan_31_to_feb_in_a_common_year():
    assert add_months(date(2023, 1, 31), 1) == date(2023, 2, 28)


def test_31st_to_a_30_day_month():
    assert add_months(date(2023, 3, 31), 1) == date(2023, 4, 30)


def test_30th_to_february():
    assert add_months(date(2023, 11, 30), 3) == date(2024, 2, 29)


def test_clamp_does_not_carry_into_later_months():
    assert add_months(date(2023, 1, 31), 2) == date(2023, 3, 31)


def test_zero_months_returns_the_start():
    assert add_months(date(2023, 10, 31), 0) == date(2023, 10, 31)


def test_29th_in_a_leap_year_to_common_february():
    assert add_months(date(2024, 2, 29), 12) == date(2025, 2, 28)


def test_next_billing_date_from_the_31st():
    assert next_billing_date(date(2023, 1, 31), date(2023, 2, 1)) == date(2023, 2, 28)


def test_billing_dates_from_the_31st():
    assert billing_dates(date(2024, 1, 31), 3) == [
        date(2024, 1, 31),
        date(2024, 2, 29),
        date(2024, 3, 31),
    ]


def test_days_until_billing_from_the_31st():
    assert days_until_billing(date(2023, 1, 31), date(2023, 2, 20)) == 8
