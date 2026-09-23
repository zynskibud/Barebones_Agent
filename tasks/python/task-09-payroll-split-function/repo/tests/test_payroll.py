from payroll import pay_slip, pay_slips


def test_pay_slip_regular_hours():
    employee = {"name": "Ann", "hours": 40, "rate": 10}
    assert pay_slip(employee) == "Ann: gross 400.00, tax 40.00, net 360.00"


def test_pay_slip_with_overtime():
    employee = {"name": "Bob", "hours": 50, "rate": 20}
    assert pay_slip(employee) == "Bob: gross 1100.00, tax 170.00, net 930.00"


def test_pay_slips_returns_one_line_each():
    employees = [
        {"name": "Ann", "hours": 40, "rate": 10},
        {"name": "Bob", "hours": 50, "rate": 20},
    ]
    assert pay_slips(employees) == [
        "Ann: gross 400.00, tax 40.00, net 360.00",
        "Bob: gross 1100.00, tax 170.00, net 930.00",
    ]
