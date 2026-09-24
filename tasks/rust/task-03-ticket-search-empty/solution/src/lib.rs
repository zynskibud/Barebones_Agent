//! Look up ticket ids in a sorted list.
//!
//! The list holds ticket ids in ascending order.

/// Return the index of `ticket_id` in the sorted list, or None.
pub fn find_ticket(ticket_ids: &[u32], ticket_id: u32) -> Option<usize> {
    if ticket_ids.is_empty() {
        return None;
    }
    if ticket_id < ticket_ids[0] || ticket_id > ticket_ids[ticket_ids.len() - 1] {
        return None;
    }
    let mut low = 0;
    let mut high = ticket_ids.len() - 1;
    while low <= high {
        let middle = (low + high) / 2;
        if ticket_ids[middle] == ticket_id {
            return Some(middle);
        }
        if ticket_ids[middle] < ticket_id {
            low = middle + 1;
        } else {
            high = middle - 1;
        }
    }
    None
}

/// Return true if the id is in the list.
pub fn has_ticket(ticket_ids: &[u32], ticket_id: u32) -> bool {
    find_ticket(ticket_ids, ticket_id).is_some()
}

/// Return the wanted ids that are not in the sorted list.
pub fn missing_tickets(ticket_ids: &[u32], wanted: &[u32]) -> Vec<u32> {
    wanted
        .iter()
        .copied()
        .filter(|&ticket_id| !has_ticket(ticket_ids, ticket_id))
        .collect()
}

/// Insert the id and keep the list sorted. Ignore duplicates.
pub fn add_ticket(ticket_ids: &mut Vec<u32>, ticket_id: u32) {
    if has_ticket(ticket_ids, ticket_id) {
        return;
    }
    ticket_ids.push(ticket_id);
    ticket_ids.sort();
}
