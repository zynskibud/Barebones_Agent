import { test } from "node:test";
import assert from "node:assert/strict";
import { byCourse, cheapest, formatMenu, itemNames, underPrice } from "../menu.ts";

const MENU = [
  { name: "Soup", price: 4.5, course: "starter" },
  { name: "Steak", price: 18.0, course: "main" },
  { name: "Pasta", price: 11.0, course: "main" },
  { name: "Cake", price: 6.0, course: "dessert" },
];

test("itemNames", () => {
  assert.deepEqual(itemNames(MENU), ["Soup", "Steak", "Pasta", "Cake"]);
});

test("cheapest", () => {
  assert.equal(cheapest(MENU)?.name, "Soup");
  assert.equal(cheapest([]), null);
});

test("byCourse", () => {
  assert.deepEqual(itemNames(byCourse(MENU, "main")), ["Steak", "Pasta"]);
});

test("underPrice", () => {
  assert.deepEqual(itemNames(underPrice(MENU, 6.0)), ["Soup", "Cake"]);
});

test("formatMenu", () => {
  assert.equal(formatMenu(MENU.slice(0, 2)), "Soup - 4.50\nSteak - 18.00");
});
