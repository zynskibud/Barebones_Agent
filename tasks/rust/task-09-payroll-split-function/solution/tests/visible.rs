use payroll::{pay_slip, pay_slips, Employee};

#[test]
fn pay_slip_regular_hours() {
    let employee = Employee::new("Ann", 40.0, 10.0);
    assert_eq!(
        pay_slip(&employee),
        "Ann: gross 400.00, tax 40.00, net 360.00"
    );
}

#[test]
fn pay_slip_with_overtime() {
    let employee = Employee::new("Bob", 50.0, 20.0);
    assert_eq!(
        pay_slip(&employee),
        "Bob: gross 1100.00, tax 170.00, net 930.00"
    );
}

#[test]
fn pay_slips_returns_one_line_each() {
    let employees = vec![
        Employee::new("Ann", 40.0, 10.0),
        Employee::new("Bob", 50.0, 20.0),
    ];
    assert_eq!(
        pay_slips(&employees),
        [
            "Ann: gross 400.00, tax 40.00, net 360.00",
            "Bob: gross 1100.00, tax 170.00, net 930.00",
        ]
    );
}
