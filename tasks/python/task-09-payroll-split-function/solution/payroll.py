"""Weekly pay slips.

An employee is a dict with a name, the hours worked this week, and
the hourly rate.
"""

REGULAR_HOURS = 40
OVERTIME_RATE = 1.5


def gross_pay(employee):
    """Return the gross pay for the week, with overtime."""
    hours = employee["hours"]
    rate = employee["rate"]
    if hours > REGULAR_HOURS:
        overtime = hours - REGULAR_HOURS
        return REGULAR_HOURS * rate + overtime * rate * OVERTIME_RATE
    return hours * rate


def tax_owed(gross):
    """Return the tax for a gross amount."""
    if gross <= 500:
        return gross * 0.10
    if gross <= 1500:
        return 50 + (gross - 500) * 0.20
    return 250 + (gross - 1500) * 0.30


def pay_slip(employee):
    """Return one line with the gross pay, the tax, and the net pay."""
    gross = gross_pay(employee)
    tax = tax_owed(gross)
    net = gross - tax
    name = employee["name"]
    return f"{name}: gross {gross:.2f}, tax {tax:.2f}, net {net:.2f}"


def pay_slips(employees):
    """Return one pay slip line for each employee."""
    return [pay_slip(employee) for employee in employees]


def print_pay_slips(employees):
    """Print every pay slip, one per line."""
    for line in pay_slips(employees):
        print(line)
