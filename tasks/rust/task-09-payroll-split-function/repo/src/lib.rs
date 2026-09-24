//! Weekly pay slips.
//!
//! An employee has a name, the hours worked this week, and the hourly rate.

pub const REGULAR_HOURS: f64 = 40.0;
pub const OVERTIME_RATE: f64 = 1.5;

/// One employee and the hours worked this week.
#[derive(Debug, Clone, PartialEq)]
pub struct Employee {
    pub name: String,
    pub hours: f64,
    pub rate: f64,
}

impl Employee {
    /// Return a new employee.
    pub fn new(name: &str, hours: f64, rate: f64) -> Employee {
        Employee {
            name: name.to_string(),
            hours,
            rate,
        }
    }
}

/// Return one line with the gross pay, the tax, and the net pay.
pub fn pay_slip(employee: &Employee) -> String {
    let hours = employee.hours;
    let rate = employee.rate;
    let gross = if hours > REGULAR_HOURS {
        let overtime = hours - REGULAR_HOURS;
        REGULAR_HOURS * rate + overtime * rate * OVERTIME_RATE
    } else {
        hours * rate
    };
    let tax = if gross <= 500.0 {
        gross * 0.10
    } else if gross <= 1500.0 {
        50.0 + (gross - 500.0) * 0.20
    } else {
        250.0 + (gross - 1500.0) * 0.30
    };
    let net = gross - tax;
    let name = &employee.name;
    format!("{name}: gross {gross:.2}, tax {tax:.2}, net {net:.2}")
}

/// Return one pay slip line for each employee.
pub fn pay_slips(employees: &[Employee]) -> Vec<String> {
    employees.iter().map(pay_slip).collect()
}

/// Print every pay slip, one per line.
pub fn print_pay_slips(employees: &[Employee]) {
    for line in pay_slips(employees) {
        println!("{line}");
    }
}
