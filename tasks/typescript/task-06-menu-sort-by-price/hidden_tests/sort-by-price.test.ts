import { test } from "node:test";
import assert from "node:assert/strict";
import { cheapest, itemNames, sortByPrice } from "../menu.ts";
import type { MenuItem } from "../menu.ts";

function makeMenu(): MenuItem[] {
  return [
    { name: "Steak", price: 18.0, course: "main" },
    { name: "Soup", price: 4.5, course: "starter" },
    { name: "Cake", price: 6.0, course: "dessert" },
    { name: "Pasta", price: 11.0, course: "main" },
  ];
}

test("orders from lowest to highest", () => {
  assert.deepEqual(itemNames(sortByPrice(makeMenu())), ["Soup", "Cake", "Pasta", "Steak"]);
});

test("returns the same item objects", () => {
  const menu = makeMenu();
  const result = sortByPrice(menu);
  assert.equal(result[0], menu[1]);
  assert.equal(result[result.length - 1], menu[0]);
});

test("equal prices keep their original order", () => {
  const menu = [
    { name: "Tea", price: 2.0, course: "drink" },
    { name: "Water", price: 1.0, course: "drink" },
    { name: "Coffee", price: 2.0, course: "drink" },
    { name: "Juice", price: 2.0, course: "drink" },
  ];
  assert.deepEqual(itemNames(sortByPrice(menu)), ["Water", "Tea", "Coffee", "Juice"]);
});

test("input array does not change", () => {
  const menu = makeMenu();
  const before = structuredClone(menu);
  sortByPrice(menu);
  assert.deepEqual(menu, before);
});

test("returns a new array", () => {
  const menu = makeMenu();
  assert.notEqual(sortByPrice(menu), menu);
});

test("empty menu", () => {
  assert.deepEqual(sortByPrice([]), []);
});

test("single item", () => {
  const menu = makeMenu().slice(0, 1);
  assert.deepEqual(sortByPrice(menu), menu);
});

test("cheapest still works", () => {
  assert.equal(cheapest(makeMenu())?.name, "Soup");
});
