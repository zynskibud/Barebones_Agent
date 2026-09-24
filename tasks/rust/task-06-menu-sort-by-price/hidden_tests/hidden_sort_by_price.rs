use std::ptr;

use menu::{cheapest, item_names, sort_by_price, MenuItem};

fn make_menu() -> Vec<MenuItem> {
    vec![
        MenuItem::new("Steak", 18.0, "main"),
        MenuItem::new("Soup", 4.5, "starter"),
        MenuItem::new("Cake", 6.0, "dessert"),
        MenuItem::new("Pasta", 11.0, "main"),
    ]
}

#[test]
fn orders_from_lowest_to_highest() {
    let menu = make_menu();
    assert_eq!(
        item_names(sort_by_price(&menu)),
        ["Soup", "Cake", "Pasta", "Steak"]
    );
}

#[test]
fn returns_the_same_items() {
    let menu = make_menu();
    let result = sort_by_price(&menu);
    assert!(ptr::eq(result[0], &menu[1]));
    assert!(ptr::eq(result[result.len() - 1], &menu[0]));
}

#[test]
fn equal_prices_keep_their_original_order() {
    let menu = vec![
        MenuItem::new("Tea", 2.0, "drink"),
        MenuItem::new("Water", 1.0, "drink"),
        MenuItem::new("Coffee", 2.0, "drink"),
        MenuItem::new("Juice", 2.0, "drink"),
    ];
    assert_eq!(
        item_names(sort_by_price(&menu)),
        ["Water", "Tea", "Coffee", "Juice"]
    );
}

#[test]
fn input_list_does_not_change() {
    let menu = make_menu();
    let before = menu.clone();
    sort_by_price(&menu);
    assert_eq!(menu, before);
}

#[test]
fn returns_a_new_list() {
    let menu = make_menu();
    let mut result: Vec<&MenuItem> = sort_by_price(&menu);
    result.pop();
    assert_eq!(result.len(), 3);
    assert_eq!(menu.len(), 4);
}

#[test]
fn empty_menu() {
    assert!(sort_by_price(&[]).is_empty());
}

#[test]
fn single_item() {
    let menu = make_menu()[..1].to_vec();
    assert_eq!(sort_by_price(&menu), vec![&menu[0]]);
}

#[test]
fn cheapest_still_works() {
    let menu = make_menu();
    assert_eq!(cheapest(&menu).unwrap().name, "Soup");
}
