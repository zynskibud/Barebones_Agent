/**
 * Weekly pay slips.
 *
 * An employee has a name, the hours worked this week, and
 * the hourly rate.
 */

export type Employee = {
  name: string;
  hours: number;
  rate: number;
};

const REGULAR_HOURS = 40;
const OVERTIME_RATE = 1.5;

/** Return one line with the gross pay, the tax, and the net pay. */
export function paySlip(employee: Employee): string {
  const hours = employee.hours;
  const rate = employee.rate;
  let gross: number;
  if (hours > REGULAR_HOURS) {
    const overtime = hours - REGULAR_HOURS;
    gross = REGULAR_HOURS * rate + overtime * rate * OVERTIME_RATE;
  } else {
    gross = hours * rate;
  }
  let tax: number;
  if (gross <= 500) {
    tax = gross * 0.1;
  } else if (gross <= 1500) {
    tax = 50 + (gross - 500) * 0.2;
  } else {
    tax = 250 + (gross - 1500) * 0.3;
  }
  const net = gross - tax;
  const name = employee.name;
  return `${name}: gross ${gross.toFixed(2)}, tax ${tax.toFixed(2)}, net ${net.toFixed(2)}`;
}

/** Return one pay slip line for each employee. */
export function paySlips(employees: Employee[]): string[] {
  return employees.map((employee) => paySlip(employee));
}

/** Print every pay slip, one per line. */
export function printPaySlips(employees: Employee[]): void {
  for (const line of paySlips(employees)) {
    console.log(line);
  }
}
