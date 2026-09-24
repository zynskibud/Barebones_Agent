import { test } from "node:test";
import assert from "node:assert/strict";
import { paySlip, paySlips } from "../payroll.ts";

test("paySlip regular hours", () => {
  const employee = { name: "Ann", hours: 40, rate: 10 };
  assert.equal(paySlip(employee), "Ann: gross 400.00, tax 40.00, net 360.00");
});

test("paySlip with overtime", () => {
  const employee = { name: "Bob", hours: 50, rate: 20 };
  assert.equal(paySlip(employee), "Bob: gross 1100.00, tax 170.00, net 930.00");
});

test("paySlips returns one line each", () => {
  const employees = [
    { name: "Ann", hours: 40, rate: 10 },
    { name: "Bob", hours: 50, rate: 20 },
  ];
  assert.deepEqual(paySlips(employees), [
    "Ann: gross 400.00, tax 40.00, net 360.00",
    "Bob: gross 1100.00, tax 170.00, net 930.00",
  ]);
});
