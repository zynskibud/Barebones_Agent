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

/// Return the gross pay for the week, with overtime.
pub fn gross_pay(employee: &Employee) -> f64 {
    let hours = employee.hours;
    let rate = employee.rate;
    if hours > REGULAR_HOURS {
        let overtime = hours - REGULAR_HOURS;
        return REGULAR_HOURS * rate + overtime * rate * OVERTIME_RATE;
    }
    hours * rate
}

/// Return the tax for a gross amount.
pub fn tax_owed(gross: f64) -> f64 {
    if gross <= 500.0 {
        return gross * 0.10;
    }
    if gross <= 1500.0 {
        return 50.0 + (gross - 500.0) * 0.20;
    }
    250.0 + (gross - 1500.0) * 0.30
}

/// Return one line with the gross pay, the tax, and the net pay.
pub fn pay_slip(employee: &Employee) -> String {
    let gross = gross_pay(employee);
    let tax = tax_owed(gross);
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
