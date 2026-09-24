/**
 * Billing dates for monthly subscriptions.
 *
 * Every date is a Date at midnight UTC, for example new Date("2024-01-31").
 */

const DAY_MS = 24 * 60 * 60 * 1000;

/**
 * Return the date `months` after `start`.
 *
 * The day stays the same when it exists. Otherwise it is the last day
 * of the target month.
 */
export function addMonths(start: Date, months: number): Date {
  const monthIndex = start.getUTCMonth() + months;
  const year = start.getUTCFullYear() + Math.floor(monthIndex / 12);
  const month = monthIndex % 12;
  const lastDay = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
  const day = Math.min(start.getUTCDate(), lastDay);
  return new Date(Date.UTC(year, month, day));
}

/** Return the first billing date that is on or after `today`. */
export function nextBillingDate(start: Date, today: Date): Date {
  let billing = start;
  let months = 0;
  while (billing < today) {
    months += 1;
    billing = addMonths(start, months);
  }
  return billing;
}

/** Return the first `count` billing dates, starting with `start`. */
export function billingDates(start: Date, count: number): Date[] {
  return Array.from({ length: count }, (_, i) => addMonths(start, i));
}

/** Return how many days remain until the next billing date. */
export function daysUntilBilling(start: Date, today: Date): number {
  const next = nextBillingDate(start, today);
  return Math.round((next.getTime() - today.getTime()) / DAY_MS);
}
