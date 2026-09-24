import { test } from "node:test";
import assert from "node:assert/strict";
import { largestExpense, makeExpense, total, totalByCategory } from "../expenses.ts";
import { formatReport } from "../report.ts";

function makeExpenses() {
  return [
    makeExpense("Train", "Travel", 150.0),
    makeExpense("Laptop", "Office", 1200.0),
    makeExpense("Paper", "Office", 50.0),
  ];
}

test("largestExpense returns the highest amount", () => {
  const expenses = makeExpenses();
  assert.equal(largestExpense(expenses), expenses[1]);
});

test("largestExpense with one expense", () => {
  const expenses = [makeExpense("Coffee", "Food", 3.5)];
  assert.deepEqual(largestExpense(expenses), expenses[0]);
});

test("largestExpense when the largest is last", () => {
  const expenses = [makeExpense("Pen", "Office", 2.0), makeExpense("Desk", "Office", 300.0)];
  assert.equal(largestExpense(expenses).description, "Desk");
});

test("report ends with the largest line", () => {
  const expected = [
    "Expense report",
    "Travel: 150.00",
    "Office: 1250.00",
    "Total: 1400.00",
    "Largest: Laptop 1200.00",
  ].join("\n");
  assert.equal(formatReport(makeExpenses()), expected);
});

test("report largest line uses two decimals", () => {
  const expenses = [makeExpense("Coffee", "Food", 3.5)];
  const lines = formatReport(expenses).split("\n");
  assert.equal(lines[lines.length - 1], "Largest: Coffee 3.50");
});

test("existing totals still work", () => {
  const expenses = makeExpenses();
  assert.equal(total(expenses), 1400.0);
  assert.deepEqual(
    totalByCategory(expenses),
    new Map([
      ["Travel", 150.0],
      ["Office", 1250.0],
    ]),
  );
});
