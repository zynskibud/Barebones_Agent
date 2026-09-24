//! Build a plain-text expense report.

use crate::expenses::{categories, largest_expense, total, total_by_category, Expense};

/// Return one report line, with the amount to two decimals.
pub fn format_line(label: &str, amount: f64) -> String {
    format!("{label}: {amount:.2}")
}

/// Return the report as one string.
///
/// The first line is the title. Then there is one line per category,
/// in the order the categories first appear. Then comes the total, and
/// the last line names the largest expense.
pub fn format_report(expenses: &[Expense]) -> String {
    let mut lines = vec!["Expense report".to_string()];
    let totals = total_by_category(expenses);
    for category in categories(expenses) {
        lines.push(format_line(&category, totals[&category]));
    }
    lines.push(format_line("Total", total(expenses)));
    if let Some(largest) = largest_expense(expenses) {
        lines.push(format!(
            "Largest: {} {:.2}",
            largest.description, largest.amount
        ));
    }
    lines.join("\n")
}

/// Print the report to the screen.
pub fn print_report(expenses: &[Expense]) {
    println!("{}", format_report(expenses));
}
