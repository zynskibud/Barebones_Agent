use cart::{add_item, item_count, make_cart, remove_item, Item};

#[test]
fn add_item_stores_the_fields() {
    let mut cart = make_cart();
    add_item(&mut cart, "pen", 2.0, 3);
    let expected = Item {
        name: "pen".to_string(),
        price: 2.0,
        quantity: 3,
    };
    assert_eq!(cart, vec![expected]);
}

#[test]
fn add_item_keeps_a_quantity_of_one() {
    let mut cart = make_cart();
    add_item(&mut cart, "pad", 5.0, 1);
    assert_eq!(cart[0].quantity, 1);
}

#[test]
fn item_count_sums_the_quantities() {
    let mut cart = make_cart();
    add_item(&mut cart, "pen", 2.0, 3);
    add_item(&mut cart, "pad", 5.0, 1);
    assert_eq!(item_count(&cart), 4);
}

#[test]
fn remove_item_drops_the_name() {
    let mut cart = make_cart();
    add_item(&mut cart, "pen", 2.0, 3);
    add_item(&mut cart, "pad", 5.0, 1);
    remove_item(&mut cart, "pen");
    let names: Vec<&str> = cart.iter().map(|item| item.name.as_str()).collect();
    assert_eq!(names, ["pad"]);
}
