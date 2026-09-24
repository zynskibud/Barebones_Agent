import { test } from "node:test";
import assert from "node:assert/strict";
import { addTicket, findTicket, hasTicket, missingTickets } from "../tickets.ts";
import type { Ticket } from "../tickets.ts";

function makeTickets(ids: number[]): Ticket[] {
  return ids.map((id) => ({ id, title: `Ticket ${id}` }));
}

const TICKETS = makeTickets([3, 8, 15, 21, 42, 57]);

test("findTicket in the middle", () => {
  assert.equal(findTicket(TICKETS, 21), 3);
});

test("findTicket at the ends", () => {
  assert.equal(findTicket(TICKETS, 3), 0);
  assert.equal(findTicket(TICKETS, 57), 5);
});

test("findTicket missing returns -1", () => {
  assert.equal(findTicket(TICKETS, 20), -1);
  assert.equal(findTicket(TICKETS, 100), -1);
});

test("hasTicket", () => {
  assert.equal(hasTicket(TICKETS, 8), true);
  assert.equal(hasTicket(TICKETS, 9), false);
});

test("missingTickets", () => {
  assert.deepEqual(missingTickets(TICKETS, [8, 9, 42, 43]), [9, 43]);
});

test("addTicket keeps the list sorted", () => {
  const tickets = makeTickets([3, 8, 15]);
  addTicket(tickets, { id: 10, title: "Ticket 10" });
  addTicket(tickets, { id: 8, title: "Another 8" });
  assert.deepEqual(tickets.map((ticket) => ticket.id), [3, 8, 10, 15]);
});
