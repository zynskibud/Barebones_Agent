use billing::{add_months, billing_dates, days_until_billing, next_billing_date, Date};

fn date(year: i32, month: u32, day: u32) -> Date {
    Date::new(year, month, day).unwrap()
}

#[test]
fn mid_month_is_unchanged() {
    assert_eq!(add_months(date(2024, 1, 15), 1), date(2024, 2, 15));
}

#[test]
fn jan_31_to_feb_in_a_leap_year() {
    assert_eq!(add_months(date(2024, 1, 31), 1), date(2024, 2, 29));
}

#[test]
fn jan_31_to_feb_in_a_common_year() {
    assert_eq!(add_months(date(2023, 1, 31), 1), date(2023, 2, 28));
}

#[test]
fn day_31_to_a_30_day_month() {
    assert_eq!(add_months(date(2023, 3, 31), 1), date(2023, 4, 30));
}

#[test]
fn day_30_to_february() {
    assert_eq!(add_months(date(2023, 11, 30), 3), date(2024, 2, 29));
}

#[test]
fn clamp_does_not_carry_into_later_months() {
    assert_eq!(add_months(date(2023, 1, 31), 2), date(2023, 3, 31));
}

#[test]
fn zero_months_returns_the_start() {
    assert_eq!(add_months(date(2023, 10, 31), 0), date(2023, 10, 31));
}

#[test]
fn day_29_in_a_leap_year_to_common_february() {
    assert_eq!(add_months(date(2024, 2, 29), 12), date(2025, 2, 28));
}

#[test]
fn next_billing_date_from_the_31st() {
    assert_eq!(
        next_billing_date(date(2023, 1, 31), date(2023, 2, 1)),
        date(2023, 2, 28)
    );
}

#[test]
fn billing_dates_from_the_31st() {
    assert_eq!(
        billing_dates(date(2024, 1, 31), 3),
        vec![date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 31)]
    );
}

#[test]
fn days_until_billing_from_the_31st() {
    assert_eq!(days_until_billing(date(2023, 1, 31), date(2023, 2, 20)), 8);
}
