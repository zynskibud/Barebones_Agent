use std::collections::BTreeMap;
use std::ptr;

use expense_report::expenses::{largest_expense, make_expense, total, total_by_category, Expense};
use expense_report::report::format_report;

fn make_expenses() -> Vec<Expense> {
    vec![
        make_expense("Train", "Travel", 150.0),
        make_expense("Laptop", "Office", 1200.0),
        make_expense("Paper", "Office", 50.0),
    ]
}

#[test]
fn largest_expense_returns_the_highest_amount() {
    let expenses = make_expenses();
    let largest = largest_expense(&expenses).unwrap();
    assert!(ptr::eq(largest, &expenses[1]));
}

#[test]
fn largest_expense_with_one_expense() {
    let expenses = vec![make_expense("Coffee", "Food", 3.5)];
    assert_eq!(largest_expense(&expenses), Some(&expenses[0]));
}

#[test]
fn largest_expense_when_the_largest_is_last() {
    let expenses = vec![
        make_expense("Pen", "Office", 2.0),
        make_expense("Desk", "Office", 300.0),
    ];
    assert_eq!(largest_expense(&expenses).unwrap().description, "Desk");
}

#[test]
fn report_ends_with_the_largest_line() {
    let expected = [
        "Expense report",
        "Travel: 150.00",
        "Office: 1250.00",
        "Total: 1400.00",
        "Largest: Laptop 1200.00",
    ]
    .join("\n");
    assert_eq!(format_report(&make_expenses()), expected);
}

#[test]
fn report_largest_line_uses_two_decimals() {
    let expenses = vec![make_expense("Coffee", "Food", 3.5)];
    let report = format_report(&expenses);
    assert_eq!(report.lines().last(), Some("Largest: Coffee 3.50"));
}

#[test]
fn existing_totals_still_work() {
    let expenses = make_expenses();
    assert_eq!(total(&expenses), 1400.0);
    let expected = BTreeMap::from([
        ("Travel".to_string(), 150.0),
        ("Office".to_string(), 1250.0),
    ]);
    assert_eq!(total_by_category(&expenses), expected);
}
