import { test } from "node:test";
import assert from "node:assert/strict";
import { addItem, sell, stockValue } from "../inventory.ts";
import type { Inventory } from "../inventory.ts";

test("negative price throws RangeError", () => {
  const inventory: Inventory = new Map();
  assert.throws(() => addItem(inventory, "A1", -1.0, 5), RangeError);
});

test("small negative float throws RangeError", () => {
  const inventory: Inventory = new Map();
  assert.throws(() => addItem(inventory, "A1", -0.01), RangeError);
});

test("negative price does not add the item", () => {
  const inventory: Inventory = new Map();
  try {
    addItem(inventory, "A1", -5, 2);
  } catch (error) {
    if (!(error instanceof RangeError)) {
      throw error;
    }
  }
  assert.equal(inventory.has("A1"), false);
});

test("zero price is allowed", () => {
  const inventory: Inventory = new Map();
  addItem(inventory, "FREE", 0, 3);
  assert.deepEqual(inventory.get("FREE"), { price: 0, quantity: 3 });
});

test("positive price is allowed", () => {
  const inventory: Inventory = new Map();
  addItem(inventory, "A1", 2.5, 10);
  assert.deepEqual(inventory.get("A1"), { price: 2.5, quantity: 10 });
});

test("duplicate SKU still throws", () => {
  const inventory: Inventory = new Map();
  addItem(inventory, "A1", 2.5);
  assert.throws(() => addItem(inventory, "A1", 3.0), Error);
});

test("other functions still work", () => {
  const inventory: Inventory = new Map();
  addItem(inventory, "A1", 2.0, 4);
  sell(inventory, "A1", 1);
  assert.equal(stockValue(inventory), 6.0);
});
