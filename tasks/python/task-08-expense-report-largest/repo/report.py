"""Build a plain-text expense report."""

from expenses import categories, total, total_by_category


def format_line(label, amount):
    """Return one report line, with the amount to two decimals."""
    return f"{label}: {amount:.2f}"


def format_report(expenses):
    """Return the report as one string.

    The first line is the title. Then there is one line per category,
    in the order the categories first appear. The last line is the total.
    """
    lines = ["Expense report"]
    totals = total_by_category(expenses)
    for category in categories(expenses):
        lines.append(format_line(category, totals[category]))
    lines.append(format_line("Total", total(expenses)))
    return "\n".join(lines)


def print_report(expenses):
    """Print the report to the screen."""
    print(format_report(expenses))
