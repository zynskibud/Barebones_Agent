import { test } from "node:test";
import assert from "node:assert/strict";
import { grossPay, paySlip, paySlips, taxOwed } from "../payroll.ts";

const ANN = { name: "Ann", hours: 40, rate: 10 };
const BOB = { name: "Bob", hours: 50, rate: 20 };
const CY = { name: "Cy", hours: 60, rate: 25 };

function assertClose(actual: number, expected: number): void {
  assert.ok(Math.abs(actual - expected) < 1e-6, `${actual} is not close to ${expected}`);
}

test("grossPay regular hours", () => {
  assertClose(grossPay(ANN), 400.0);
});

test("grossPay with overtime", () => {
  assertClose(grossPay({ name: "X", hours: 45, rate: 10 }), 475.0);
});

test("grossPay part time", () => {
  assertClose(grossPay({ name: "X", hours: 20, rate: 12.5 }), 250.0);
});

test("taxOwed low band", () => {
  assertClose(taxOwed(400), 40.0);
  assertClose(taxOwed(500), 50.0);
});

test("taxOwed middle band", () => {
  assertClose(taxOwed(1000), 150.0);
  assertClose(taxOwed(1500), 250.0);
});

test("taxOwed top band", () => {
  assertClose(taxOwed(2000), 400.0);
});

test("paySlip output is unchanged", () => {
  assert.equal(paySlip(ANN), "Ann: gross 400.00, tax 40.00, net 360.00");
  assert.equal(paySlip(BOB), "Bob: gross 1100.00, tax 170.00, net 930.00");
  assert.equal(paySlip(CY), "Cy: gross 1750.00, tax 325.00, net 1425.00");
});

test("paySlips still works", () => {
  assert.deepEqual(paySlips([ANN, BOB]), [
    "Ann: gross 400.00, tax 40.00, net 360.00",
    "Bob: gross 1100.00, tax 170.00, net 930.00",
  ]);
});

test("paySlip calls grossPay and taxOwed", () => {
  const source = paySlip.toString();
  assert.match(source, /\bgrossPay\s*\(/);
  assert.match(source, /\btaxOwed\s*\(/);
});
