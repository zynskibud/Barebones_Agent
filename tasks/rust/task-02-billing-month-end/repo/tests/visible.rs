use billing::{add_months, billing_dates, days_until_billing, next_billing_date, Date};

fn date(year: i32, month: u32, day: u32) -> Date {
    Date::new(year, month, day).unwrap()
}

#[test]
fn add_months_mid_month() {
    assert_eq!(add_months(date(2024, 1, 15), 1), date(2024, 2, 15));
}

#[test]
fn add_months_crosses_the_year() {
    assert_eq!(add_months(date(2024, 11, 10), 3), date(2025, 2, 10));
}

#[test]
fn next_billing_date_skips_past_dates() {
    assert_eq!(
        next_billing_date(date(2024, 1, 5), date(2024, 3, 6)),
        date(2024, 4, 5)
    );
}

#[test]
fn billing_dates_lists_each_month() {
    assert_eq!(
        billing_dates(date(2024, 1, 5), 3),
        vec![date(2024, 1, 5), date(2024, 2, 5), date(2024, 3, 5)]
    );
}

#[test]
fn days_until_billing_counts_the_days() {
    assert_eq!(days_until_billing(date(2024, 1, 5), date(2024, 1, 1)), 4);
}
