use inventory::{add_item, sell, stock_value, Inventory, StockItem};

#[test]
fn negative_price_returns_an_error() {
    let mut inventory = Inventory::new();
    assert!(add_item(&mut inventory, "A1", -1.0, 5).is_err());
}

#[test]
fn small_negative_float_returns_an_error() {
    let mut inventory = Inventory::new();
    assert!(add_item(&mut inventory, "A1", -0.01, 0).is_err());
}

#[test]
fn negative_price_does_not_add_the_item() {
    let mut inventory = Inventory::new();
    let _ = add_item(&mut inventory, "A1", -5.0, 2);
    assert!(!inventory.contains_key("A1"));
}

#[test]
fn zero_price_is_allowed() {
    let mut inventory = Inventory::new();
    assert!(add_item(&mut inventory, "FREE", 0.0, 3).is_ok());
    let expected = StockItem {
        price: 0.0,
        quantity: 3,
    };
    assert_eq!(inventory["FREE"], expected);
}

#[test]
fn positive_price_is_allowed() {
    let mut inventory = Inventory::new();
    assert!(add_item(&mut inventory, "A1", 2.5, 10).is_ok());
    let expected = StockItem {
        price: 2.5,
        quantity: 10,
    };
    assert_eq!(inventory["A1"], expected);
}

#[test]
fn duplicate_sku_still_returns_an_error() {
    let mut inventory = Inventory::new();
    add_item(&mut inventory, "A1", 2.5, 0).unwrap();
    assert!(add_item(&mut inventory, "A1", 3.0, 0).is_err());
}

#[test]
fn other_functions_still_work() {
    let mut inventory = Inventory::new();
    add_item(&mut inventory, "A1", 2.0, 4).unwrap();
    sell(&mut inventory, "A1", 1).unwrap();
    assert_eq!(stock_value(&inventory), 6.0);
}
