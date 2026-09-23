import pytest

import payroll
from payroll import gross_pay, pay_slip, pay_slips, tax_owed

ANN = {"name": "Ann", "hours": 40, "rate": 10}
BOB = {"name": "Bob", "hours": 50, "rate": 20}
CY = {"name": "Cy", "hours": 60, "rate": 25}


def test_gross_pay_regular_hours():
    assert gross_pay(ANN) == pytest.approx(400.0)


def test_gross_pay_with_overtime():
    assert gross_pay({"name": "X", "hours": 45, "rate": 10}) == pytest.approx(475.0)


def test_gross_pay_part_time():
    assert gross_pay({"name": "X", "hours": 20, "rate": 12.5}) == pytest.approx(250.0)


def test_tax_owed_low_band():
    assert tax_owed(400) == pytest.approx(40.0)
    assert tax_owed(500) == pytest.approx(50.0)


def test_tax_owed_middle_band():
    assert tax_owed(1000) == pytest.approx(150.0)
    assert tax_owed(1500) == pytest.approx(250.0)


def test_tax_owed_top_band():
    assert tax_owed(2000) == pytest.approx(400.0)


def test_pay_slip_output_is_unchanged():
    assert pay_slip(ANN) == "Ann: gross 400.00, tax 40.00, net 360.00"
    assert pay_slip(BOB) == "Bob: gross 1100.00, tax 170.00, net 930.00"
    assert pay_slip(CY) == "Cy: gross 1750.00, tax 325.00, net 1425.00"


def test_pay_slips_still_works():
    assert pay_slips([ANN, BOB]) == [
        "Ann: gross 400.00, tax 40.00, net 360.00",
        "Bob: gross 1100.00, tax 170.00, net 930.00",
    ]


def test_pay_slip_calls_gross_pay_and_tax_owed(monkeypatch):
    monkeypatch.setattr(payroll, "gross_pay", lambda employee: 1000.0)
    monkeypatch.setattr(payroll, "tax_owed", lambda gross: 100.0)
    assert payroll.pay_slip(ANN) == "Ann: gross 1000.00, tax 100.00, net 900.00"
