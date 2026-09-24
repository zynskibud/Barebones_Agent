use tickets::{add_ticket, find_ticket, has_ticket, missing_tickets};

const IDS: [u32; 6] = [3, 8, 15, 21, 42, 57];

#[test]
fn find_ticket_in_the_middle() {
    assert_eq!(find_ticket(&IDS, 21), Some(3));
}

#[test]
fn find_ticket_at_the_ends() {
    assert_eq!(find_ticket(&IDS, 3), Some(0));
    assert_eq!(find_ticket(&IDS, 57), Some(5));
}

#[test]
fn find_ticket_missing_returns_none() {
    assert_eq!(find_ticket(&IDS, 20), None);
    assert_eq!(find_ticket(&IDS, 100), None);
}

#[test]
fn has_ticket_checks_the_list() {
    assert!(has_ticket(&IDS, 8));
    assert!(!has_ticket(&IDS, 9));
}

#[test]
fn missing_tickets_lists_the_absent_ids() {
    assert_eq!(missing_tickets(&IDS, &[8, 9, 42, 43]), vec![9, 43]);
}

#[test]
fn add_ticket_keeps_the_list_sorted() {
    let mut ids = vec![3, 8, 15];
    add_ticket(&mut ids, 10);
    add_ticket(&mut ids, 8);
    assert_eq!(ids, vec![3, 8, 10, 15]);
}
