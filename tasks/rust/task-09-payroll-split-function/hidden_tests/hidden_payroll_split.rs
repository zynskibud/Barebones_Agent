use payroll::{gross_pay, pay_slip, pay_slips, tax_owed, Employee};

fn ann() -> Employee {
    Employee::new("Ann", 40.0, 10.0)
}

fn bob() -> Employee {
    Employee::new("Bob", 50.0, 20.0)
}

fn cy() -> Employee {
    Employee::new("Cy", 60.0, 25.0)
}

fn assert_close(actual: f64, expected: f64) {
    assert!(
        (actual - expected).abs() < 1e-6,
        "expected {expected}, got {actual}"
    );
}

#[test]
fn gross_pay_regular_hours() {
    assert_close(gross_pay(&ann()), 400.0);
}

#[test]
fn gross_pay_with_overtime() {
    assert_close(gross_pay(&Employee::new("X", 45.0, 10.0)), 475.0);
}

#[test]
fn gross_pay_part_time() {
    assert_close(gross_pay(&Employee::new("X", 20.0, 12.5)), 250.0);
}

#[test]
fn tax_owed_low_band() {
    assert_close(tax_owed(400.0), 40.0);
    assert_close(tax_owed(500.0), 50.0);
}

#[test]
fn tax_owed_middle_band() {
    assert_close(tax_owed(1000.0), 150.0);
    assert_close(tax_owed(1500.0), 250.0);
}

#[test]
fn tax_owed_top_band() {
    assert_close(tax_owed(2000.0), 400.0);
}

#[test]
fn pay_slip_output_is_unchanged() {
    assert_eq!(pay_slip(&ann()), "Ann: gross 400.00, tax 40.00, net 360.00");
    assert_eq!(
        pay_slip(&bob()),
        "Bob: gross 1100.00, tax 170.00, net 930.00"
    );
    assert_eq!(
        pay_slip(&cy()),
        "Cy: gross 1750.00, tax 325.00, net 1425.00"
    );
}

#[test]
fn pay_slips_still_works() {
    assert_eq!(
        pay_slips(&[ann(), bob()]),
        [
            "Ann: gross 400.00, tax 40.00, net 360.00",
            "Bob: gross 1100.00, tax 170.00, net 930.00",
        ]
    );
}

// Rust cannot swap out a function at run time, so this test cannot check
// that pay_slip calls gross_pay and tax_owed. It checks that the three
// functions agree for every employee instead.
#[test]
fn pay_slip_agrees_with_gross_pay_and_tax_owed() {
    for employee in [ann(), bob(), cy(), Employee::new("X", 45.0, 10.0)] {
        let gross = gross_pay(&employee);
        let tax = tax_owed(gross);
        let net = gross - tax;
        let name = &employee.name;
        let expected = format!("{name}: gross {gross:.2}, tax {tax:.2}, net {net:.2}");
        assert_eq!(pay_slip(&employee), expected);
    }
}
