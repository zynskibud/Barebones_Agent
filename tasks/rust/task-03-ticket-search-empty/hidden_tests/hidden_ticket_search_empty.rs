use tickets::{add_ticket, find_ticket, has_ticket, missing_tickets};

const IDS: [u32; 6] = [3, 8, 15, 21, 42, 57];

#[test]
fn empty_list_returns_none() {
    assert_eq!(find_ticket(&[], 5), None);
}

#[test]
fn has_ticket_on_empty_list_is_false() {
    assert!(!has_ticket(&[], 5));
}

#[test]
fn missing_tickets_on_empty_list_returns_all_wanted() {
    assert_eq!(missing_tickets(&[], &[1, 2, 3]), vec![1, 2, 3]);
}

#[test]
fn add_ticket_to_empty_list() {
    let mut ids = Vec::new();
    add_ticket(&mut ids, 7);
    assert_eq!(ids, vec![7]);
}

#[test]
fn single_item_list() {
    assert_eq!(find_ticket(&[9], 9), Some(0));
    assert_eq!(find_ticket(&[9], 4), None);
    assert_eq!(find_ticket(&[9], 12), None);
}

#[test]
fn find_ticket_still_finds_every_item() {
    for (index, ticket_id) in IDS.iter().enumerate() {
        assert_eq!(find_ticket(&IDS, *ticket_id), Some(index));
    }
}

#[test]
fn find_ticket_still_returns_none_when_missing() {
    assert_eq!(find_ticket(&IDS, 1), None);
    assert_eq!(find_ticket(&IDS, 20), None);
    assert_eq!(find_ticket(&IDS, 99), None);
}
