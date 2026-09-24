import { test } from "node:test";
import assert from "node:assert/strict";
import { addItem, cartTotal, itemCount, makeCart } from "../cart.ts";

function assertClose(actual: number, expected: number): void {
  assert.ok(Math.abs(actual - expected) < 1e-6, `${actual} is not close to ${expected}`);
}

test("total multiplies price by quantity", () => {
  const cart = makeCart();
  addItem(cart, "pen", 2, 3);
  assert.equal(cartTotal(cart), 6);
});

test("total adds several lines", () => {
  const cart = makeCart();
  addItem(cart, "pen", 2, 3);
  addItem(cart, "pad", 5, 2);
  addItem(cart, "ink", 10);
  assert.equal(cartTotal(cart), 26);
});

test("total with quantity one is the price", () => {
  const cart = makeCart();
  addItem(cart, "ink", 10);
  assert.equal(cartTotal(cart), 10);
});

test("total of an empty cart is zero", () => {
  assert.equal(cartTotal(makeCart()), 0);
});

test("total with float prices", () => {
  const cart = makeCart();
  addItem(cart, "tape", 1.5, 4);
  addItem(cart, "glue", 0.25, 2);
  assertClose(cartTotal(cart), 6.5);
});

test("itemCount still works", () => {
  const cart = makeCart();
  addItem(cart, "pen", 2, 3);
  addItem(cart, "pad", 5, 2);
  assert.equal(itemCount(cart), 5);
});
