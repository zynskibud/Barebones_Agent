"""Expense records.

Each expense is a dict with a description, a category, and an amount.
"""


def make_expense(description, category, amount):
    """Return one expense record."""
    return {"description": description, "category": category, "amount": amount}


def total(expenses):
    """Return the sum of all amounts."""
    return sum(expense["amount"] for expense in expenses)


def largest_expense(expenses):
    """Return the expense with the highest amount."""
    return max(expenses, key=lambda expense: expense["amount"])


def total_by_category(expenses):
    """Return a dict that maps each category to its total amount."""
    totals = {}
    for expense in expenses:
        category = expense["category"]
        totals[category] = totals.get(category, 0) + expense["amount"]
    return totals


def categories(expenses):
    """Return the category names in the order they first appear."""
    seen = []
    for expense in expenses:
        if expense["category"] not in seen:
            seen.append(expense["category"])
    return seen


def in_category(expenses, category):
    """Return the expenses of one category, in the original order."""
    return [expense for expense in expenses if expense["category"] == category]
