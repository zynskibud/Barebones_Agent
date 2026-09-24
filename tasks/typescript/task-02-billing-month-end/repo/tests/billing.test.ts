import { test } from "node:test";
import assert from "node:assert/strict";
import { addMonths, billingDates, daysUntilBilling, nextBillingDate } from "../billing.ts";

function day(text: string): Date {
  return new Date(text);
}

function iso(date: Date): string {
  return date.toISOString().slice(0, 10);
}

test("addMonths mid month", () => {
  assert.equal(iso(addMonths(day("2024-01-15"), 1)), "2024-02-15");
});

test("addMonths crosses the year", () => {
  assert.equal(iso(addMonths(day("2024-11-10"), 3)), "2025-02-10");
});

test("nextBillingDate skips past dates", () => {
  assert.equal(iso(nextBillingDate(day("2024-01-05"), day("2024-03-06"))), "2024-04-05");
});

test("billingDates lists each month", () => {
  assert.deepEqual(billingDates(day("2024-01-05"), 3).map(iso), [
    "2024-01-05",
    "2024-02-05",
    "2024-03-05",
  ]);
});

test("daysUntilBilling", () => {
  assert.equal(daysUntilBilling(day("2024-01-05"), day("2024-01-01")), 4);
});
