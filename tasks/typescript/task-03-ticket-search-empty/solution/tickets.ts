/**
 * Look up tickets in a list that is sorted by id.
 *
 * Each ticket has an integer id and a title. The ids are in ascending order.
 */

export type Ticket = {
  id: number;
  title: string;
};

/** Return the index of the ticket with this id in the sorted list, or -1. */
export function findTicket(tickets: Ticket[], id: number): number {
  if (tickets.length === 0) {
    return -1;
  }
  if (id < tickets[0].id || id > tickets[tickets.length - 1].id) {
    return -1;
  }
  let low = 0;
  let high = tickets.length - 1;
  while (low <= high) {
    const middle = Math.floor((low + high) / 2);
    if (tickets[middle].id === id) {
      return middle;
    }
    if (tickets[middle].id < id) {
      low = middle + 1;
    } else {
      high = middle - 1;
    }
  }
  return -1;
}

/** Return true if a ticket with this id is in the list. */
export function hasTicket(tickets: Ticket[], id: number): boolean {
  return findTicket(tickets, id) !== -1;
}

/** Return the wanted ids that have no ticket in the sorted list. */
export function missingTickets(tickets: Ticket[], wanted: number[]): number[] {
  return wanted.filter((id) => !hasTicket(tickets, id));
}

/** Insert the ticket and keep the list sorted by id. Ignore duplicate ids. */
export function addTicket(tickets: Ticket[], ticket: Ticket): void {
  if (hasTicket(tickets, ticket.id)) {
    return;
  }
  tickets.push(ticket);
  tickets.sort((a, b) => a.id - b.id);
}
