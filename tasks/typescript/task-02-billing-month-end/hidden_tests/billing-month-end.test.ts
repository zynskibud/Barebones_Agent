import { test } from "node:test";
import assert from "node:assert/strict";
import { addMonths, billingDates, daysUntilBilling, nextBillingDate } from "../billing.ts";

function day(text: string): Date {
  return new Date(text);
}

function iso(date: Date): string {
  return date.toISOString().slice(0, 10);
}

test("mid month is unchanged", () => {
  assert.equal(iso(addMonths(day("2024-01-15"), 1)), "2024-02-15");
});

test("Jan 31 to Feb in a leap year", () => {
  assert.equal(iso(addMonths(day("2024-01-31"), 1)), "2024-02-29");
});

test("Jan 31 to Feb in a common year", () => {
  assert.equal(iso(addMonths(day("2023-01-31"), 1)), "2023-02-28");
});

test("31st to a 30-day month", () => {
  assert.equal(iso(addMonths(day("2023-03-31"), 1)), "2023-04-30");
});

test("30th to February", () => {
  assert.equal(iso(addMonths(day("2023-11-30"), 3)), "2024-02-29");
});

test("clamp does not carry into later months", () => {
  assert.equal(iso(addMonths(day("2023-01-31"), 2)), "2023-03-31");
});

test("zero months returns the start", () => {
  assert.equal(iso(addMonths(day("2023-10-31"), 0)), "2023-10-31");
});

test("29th in a leap year to common February", () => {
  assert.equal(iso(addMonths(day("2024-02-29"), 12)), "2025-02-28");
});

test("nextBillingDate from the 31st", () => {
  assert.equal(iso(nextBillingDate(day("2023-01-31"), day("2023-02-01"))), "2023-02-28");
});

test("billingDates from the 31st", () => {
  assert.deepEqual(billingDates(day("2024-01-31"), 3).map(iso), [
    "2024-01-31",
    "2024-02-29",
    "2024-03-31",
  ]);
});

test("daysUntilBilling from the 31st", () => {
  assert.equal(daysUntilBilling(day("2023-01-31"), day("2023-02-20")), 8);
});
