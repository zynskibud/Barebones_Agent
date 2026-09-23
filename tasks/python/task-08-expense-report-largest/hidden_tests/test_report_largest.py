from expenses import largest_expense, make_expense, total, total_by_category
from report import format_report


def make_expenses():
    return [
        make_expense("Train", "Travel", 150.0),
        make_expense("Laptop", "Office", 1200.0),
        make_expense("Paper", "Office", 50.0),
    ]


def test_largest_expense_returns_the_highest_amount():
    expenses = make_expenses()
    assert largest_expense(expenses) is expenses[1]


def test_largest_expense_with_one_expense():
    expenses = [make_expense("Coffee", "Food", 3.5)]
    assert largest_expense(expenses) == expenses[0]


def test_largest_expense_when_the_largest_is_last():
    expenses = [
        make_expense("Pen", "Office", 2.0),
        make_expense("Desk", "Office", 300.0),
    ]
    assert largest_expense(expenses)["description"] == "Desk"


def test_report_ends_with_the_largest_line():
    expected = "\n".join(
        [
            "Expense report",
            "Travel: 150.00",
            "Office: 1250.00",
            "Total: 1400.00",
            "Largest: Laptop 1200.00",
        ]
    )
    assert format_report(make_expenses()) == expected


def test_report_largest_line_uses_two_decimals():
    expenses = [make_expense("Coffee", "Food", 3.5)]
    assert format_report(expenses).splitlines()[-1] == "Largest: Coffee 3.50"


def test_existing_totals_still_work():
    expenses = make_expenses()
    assert total(expenses) == 1400.0
    assert total_by_category(expenses) == {"Travel": 150.0, "Office": 1250.0}
