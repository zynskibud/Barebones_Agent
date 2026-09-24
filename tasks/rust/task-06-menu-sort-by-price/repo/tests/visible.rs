use menu::{by_course, cheapest, format_menu, item_names, under_price, MenuItem};

fn make_menu() -> Vec<MenuItem> {
    vec![
        MenuItem::new("Soup", 4.5, "starter"),
        MenuItem::new("Steak", 18.0, "main"),
        MenuItem::new("Pasta", 11.0, "main"),
        MenuItem::new("Cake", 6.0, "dessert"),
    ]
}

#[test]
fn item_names_keeps_menu_order() {
    assert_eq!(item_names(&make_menu()), ["Soup", "Steak", "Pasta", "Cake"]);
}

#[test]
fn cheapest_finds_the_lowest_price() {
    let menu = make_menu();
    assert_eq!(cheapest(&menu).unwrap().name, "Soup");
    assert_eq!(cheapest(&[]), None);
}

#[test]
fn by_course_filters_one_course() {
    let menu = make_menu();
    assert_eq!(item_names(by_course(&menu, "main")), ["Steak", "Pasta"]);
}

#[test]
fn under_price_filters_by_limit() {
    let menu = make_menu();
    assert_eq!(item_names(under_price(&menu, 6.0)), ["Soup", "Cake"]);
}

#[test]
fn format_menu_prints_two_decimals() {
    let menu = make_menu();
    assert_eq!(format_menu(&menu[..2]), "Soup - 4.50\nSteak - 18.00");
}
