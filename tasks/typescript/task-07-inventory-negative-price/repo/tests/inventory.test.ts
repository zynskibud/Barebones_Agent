import { test } from "node:test";
import assert from "node:assert/strict";
import { addItem, outOfStock, restock, sell, stockValue } from "../inventory.ts";
import type { Inventory } from "../inventory.ts";

function makeInventory(): Inventory {
  const inventory: Inventory = new Map();
  addItem(inventory, "A1", 2.5, 10);
  addItem(inventory, "B2", 10.0);
  return inventory;
}

test("addItem stores price and quantity", () => {
  const inventory = makeInventory();
  assert.deepEqual(inventory.get("A1"), { price: 2.5, quantity: 10 });
  assert.equal(inventory.get("B2")?.quantity, 0);
});

test("addItem rejects a duplicate SKU", () => {
  const inventory = makeInventory();
  assert.throws(() => addItem(inventory, "A1", 3.0), Error);
});

test("restock and sell", () => {
  const inventory = makeInventory();
  restock(inventory, "B2", 5);
  sell(inventory, "B2", 2);
  assert.equal(inventory.get("B2")?.quantity, 3);
});

test("sell rejects too many", () => {
  const inventory = makeInventory();
  assert.throws(() => sell(inventory, "A1", 11), RangeError);
});

test("stockValue", () => {
  assert.equal(stockValue(makeInventory()), 25.0);
});

test("outOfStock", () => {
  assert.deepEqual(outOfStock(makeInventory()), ["B2"]);
});
