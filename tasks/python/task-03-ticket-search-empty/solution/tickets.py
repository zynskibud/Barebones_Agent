"""Look up ticket ids in a sorted list.

The list holds integer ticket ids in ascending order.
"""


def find_ticket(ticket_ids, ticket_id):
    """Return the index of `ticket_id` in the sorted list, or -1."""
    if not ticket_ids:
        return -1
    if ticket_id < ticket_ids[0] or ticket_id > ticket_ids[-1]:
        return -1
    low = 0
    high = len(ticket_ids) - 1
    while low <= high:
        middle = (low + high) // 2
        if ticket_ids[middle] == ticket_id:
            return middle
        if ticket_ids[middle] < ticket_id:
            low = middle + 1
        else:
            high = middle - 1
    return -1


def has_ticket(ticket_ids, ticket_id):
    """Return True if the id is in the list."""
    return find_ticket(ticket_ids, ticket_id) != -1


def missing_tickets(ticket_ids, wanted):
    """Return the wanted ids that are not in the sorted list."""
    return [ticket_id for ticket_id in wanted if not has_ticket(ticket_ids, ticket_id)]


def add_ticket(ticket_ids, ticket_id):
    """Insert the id and keep the list sorted. Ignore duplicates."""
    if has_ticket(ticket_ids, ticket_id):
        return
    ticket_ids.append(ticket_id)
    ticket_ids.sort()
