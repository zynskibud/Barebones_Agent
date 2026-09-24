/**
 * Expense records.
 *
 * Each expense has a description, a category, and an amount.
 */

export type Expense = {
  description: string;
  category: string;
  amount: number;
};

/** Return one expense record. */
export function makeExpense(description: string, category: string, amount: number): Expense {
  return { description, category, amount };
}

/** Return the sum of all amounts. */
export function total(expenses: Expense[]): number {
  return expenses.reduce((sum, expense) => sum + expense.amount, 0);
}

/** Return a Map from each category to its total amount. */
export function totalByCategory(expenses: Expense[]): Map<string, number> {
  const totals = new Map<string, number>();
  for (const expense of expenses) {
    const category = expense.category;
    totals.set(category, (totals.get(category) ?? 0) + expense.amount);
  }
  return totals;
}

/** Return the category names in the order they first appear. */
export function categories(expenses: Expense[]): string[] {
  const seen: string[] = [];
  for (const expense of expenses) {
    if (!seen.includes(expense.category)) {
      seen.push(expense.category);
    }
  }
  return seen;
}

/** Return the expenses of one category, in the original order. */
export function inCategory(expenses: Expense[], category: string): Expense[] {
  return expenses.filter((expense) => expense.category === category);
}
