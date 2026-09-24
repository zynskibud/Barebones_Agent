import { test } from "node:test";
import assert from "node:assert/strict";
import { addItem, itemCount, makeCart, removeItem } from "../cart.ts";

test("addItem stores the fields", () => {
  const cart = makeCart();
  addItem(cart, "pen", 2, 3);
  assert.deepEqual(cart, [{ name: "pen", price: 2, quantity: 3 }]);
});

test("addItem default quantity is one", () => {
  const cart = makeCart();
  addItem(cart, "pad", 5);
  assert.equal(cart[0].quantity, 1);
});

test("itemCount sums the quantities", () => {
  const cart = makeCart();
  addItem(cart, "pen", 2, 3);
  addItem(cart, "pad", 5);
  assert.equal(itemCount(cart), 4);
});

test("removeItem drops the name", () => {
  const cart = makeCart();
  addItem(cart, "pen", 2, 3);
  addItem(cart, "pad", 5);
  removeItem(cart, "pen");
  assert.deepEqual(cart.map((item) => item.name), ["pad"]);
});
