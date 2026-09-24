//! Expense records.
//!
//! Each expense has a description, a category, and an amount.

use std::collections::BTreeMap;

/// One expense record.
#[derive(Debug, Clone, PartialEq)]
pub struct Expense {
    pub description: String,
    pub category: String,
    pub amount: f64,
}

/// Return one expense record.
pub fn make_expense(description: &str, category: &str, amount: f64) -> Expense {
    Expense {
        description: description.to_string(),
        category: category.to_string(),
        amount,
    }
}

/// Return the sum of all amounts.
pub fn total(expenses: &[Expense]) -> f64 {
    expenses.iter().map(|expense| expense.amount).sum()
}

/// Return the expense with the highest amount, or None if there are none.
pub fn largest_expense(expenses: &[Expense]) -> Option<&Expense> {
    expenses.iter().max_by(|a, b| a.amount.total_cmp(&b.amount))
}

/// Return a map from each category to its total amount.
pub fn total_by_category(expenses: &[Expense]) -> BTreeMap<String, f64> {
    let mut totals = BTreeMap::new();
    for expense in expenses {
        *totals.entry(expense.category.clone()).or_insert(0.0) += expense.amount;
    }
    totals
}

/// Return the category names in the order they first appear.
pub fn categories(expenses: &[Expense]) -> Vec<String> {
    let mut seen: Vec<String> = Vec::new();
    for expense in expenses {
        if !seen.contains(&expense.category) {
            seen.push(expense.category.clone());
        }
    }
    seen
}

/// Return the expenses of one category, in the original order.
pub fn in_category<'a>(expenses: &'a [Expense], category: &str) -> Vec<&'a Expense> {
    expenses
        .iter()
        .filter(|expense| expense.category == category)
        .collect()
}
