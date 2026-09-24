use cart::{add_item, cart_total, item_count, make_cart};

fn assert_close(actual: f64, expected: f64) {
    assert!(
        (actual - expected).abs() < 1e-9,
        "expected {expected}, got {actual}"
    );
}

#[test]
fn total_multiplies_price_by_quantity() {
    let mut cart = make_cart();
    add_item(&mut cart, "pen", 2.0, 3);
    assert_eq!(cart_total(&cart), 6.0);
}

#[test]
fn total_adds_several_lines() {
    let mut cart = make_cart();
    add_item(&mut cart, "pen", 2.0, 3);
    add_item(&mut cart, "pad", 5.0, 2);
    add_item(&mut cart, "ink", 10.0, 1);
    assert_eq!(cart_total(&cart), 26.0);
}

#[test]
fn total_with_quantity_one_is_the_price() {
    let mut cart = make_cart();
    add_item(&mut cart, "ink", 10.0, 1);
    assert_eq!(cart_total(&cart), 10.0);
}

#[test]
fn total_of_empty_cart_is_zero() {
    assert_eq!(cart_total(&make_cart()), 0.0);
}

#[test]
fn total_with_float_prices() {
    let mut cart = make_cart();
    add_item(&mut cart, "tape", 1.5, 4);
    add_item(&mut cart, "glue", 0.25, 2);
    assert_close(cart_total(&cart), 6.5);
}

#[test]
fn item_count_still_works() {
    let mut cart = make_cart();
    add_item(&mut cart, "pen", 2.0, 3);
    add_item(&mut cart, "pad", 5.0, 2);
    assert_eq!(item_count(&cart), 5);
}
