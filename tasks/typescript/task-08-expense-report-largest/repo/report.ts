/** Build a plain-text expense report. */

import { categories, total, totalByCategory } from "./expenses.ts";
import type { Expense } from "./expenses.ts";

/** Return one report line, with the amount to two decimals. */
export function formatLine(label: string, amount: number): string {
  return `${label}: ${amount.toFixed(2)}`;
}

/**
 * Return the report as one string.
 *
 * The first line is the title. Then there is one line per category,
 * in the order the categories first appear. The last line is the total.
 */
export function formatReport(expenses: Expense[]): string {
  const lines = ["Expense report"];
  const totals = totalByCategory(expenses);
  for (const category of categories(expenses)) {
    lines.push(formatLine(category, totals.get(category) ?? 0));
  }
  lines.push(formatLine("Total", total(expenses)));
  return lines.join("\n");
}

/** Print the report to the screen. */
export function printReport(expenses: Expense[]): void {
  console.log(formatReport(expenses));
}
