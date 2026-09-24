//! Billing dates for monthly subscriptions.

/// A calendar date. Dates compare by year, then month, then day.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub struct Date {
    pub year: i32,
    pub month: u32,
    pub day: u32,
}

impl Date {
    /// Return the date, or None if the month or the day does not exist.
    pub fn new(year: i32, month: u32, day: u32) -> Option<Date> {
        if month < 1 || month > 12 || day < 1 || day > days_in_month(year, month) {
            return None;
        }
        Some(Date { year, month, day })
    }
}

/// Return true if the year has a 29 February.
pub fn is_leap_year(year: i32) -> bool {
    (year % 4 == 0 && year % 100 != 0) || year % 400 == 0
}

/// Return the number of days in the month.
pub fn days_in_month(year: i32, month: u32) -> u32 {
    match month {
        2 if is_leap_year(year) => 29,
        2 => 28,
        4 | 6 | 9 | 11 => 30,
        _ => 31,
    }
}

/// Return the number of days from 1 January of year 1 to the date.
fn day_number(date: Date) -> i64 {
    let mut days = date.day as i64;
    for year in 1..date.year {
        days += if is_leap_year(year) { 366 } else { 365 };
    }
    for month in 1..date.month {
        days += days_in_month(date.year, month) as i64;
    }
    days
}

/// Return the date `months` after `start`, on the same day of the month.
pub fn add_months(start: Date, months: u32) -> Date {
    let month_index = start.month - 1 + months;
    let year = start.year + (month_index / 12) as i32;
    let month = month_index % 12 + 1;
    Date::new(year, month, start.day).expect("day is out of range for month")
}

/// Return the first billing date that is on or after `today`.
pub fn next_billing_date(start: Date, today: Date) -> Date {
    let mut billing = start;
    let mut months = 0;
    while billing < today {
        months += 1;
        billing = add_months(start, months);
    }
    billing
}

/// Return the first `count` billing dates, starting with `start`.
pub fn billing_dates(start: Date, count: u32) -> Vec<Date> {
    (0..count).map(|i| add_months(start, i)).collect()
}

/// Return how many days remain until the next billing date.
pub fn days_until_billing(start: Date, today: Date) -> i64 {
    day_number(next_billing_date(start, today)) - day_number(today)
}
