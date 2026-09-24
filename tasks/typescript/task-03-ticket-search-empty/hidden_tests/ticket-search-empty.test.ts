import { test } from "node:test";
import assert from "node:assert/strict";
import { addTicket, findTicket, hasTicket, missingTickets } from "../tickets.ts";
import type { Ticket } from "../tickets.ts";

function makeTickets(ids: number[]): Ticket[] {
  return ids.map((id) => ({ id, title: `Ticket ${id}` }));
}

const IDS = [3, 8, 15, 21, 42, 57];
const TICKETS = makeTickets(IDS);

test("empty list returns -1", () => {
  assert.equal(findTicket([], 5), -1);
});

test("hasTicket on an empty list is false", () => {
  assert.equal(hasTicket([], 5), false);
});

test("missingTickets on an empty list returns all wanted", () => {
  assert.deepEqual(missingTickets([], [1, 2, 3]), [1, 2, 3]);
});

test("addTicket to an empty list", () => {
  const tickets: Ticket[] = [];
  addTicket(tickets, { id: 7, title: "Ticket 7" });
  assert.deepEqual(tickets.map((ticket) => ticket.id), [7]);
});

test("single item list", () => {
  const tickets = makeTickets([9]);
  assert.equal(findTicket(tickets, 9), 0);
  assert.equal(findTicket(tickets, 4), -1);
  assert.equal(findTicket(tickets, 12), -1);
});

test("findTicket still finds every item", () => {
  IDS.forEach((id, index) => {
    assert.equal(findTicket(TICKETS, id), index);
  });
});

test("findTicket still returns -1 when missing", () => {
  assert.equal(findTicket(TICKETS, 1), -1);
  assert.equal(findTicket(TICKETS, 20), -1);
  assert.equal(findTicket(TICKETS, 99), -1);
});
