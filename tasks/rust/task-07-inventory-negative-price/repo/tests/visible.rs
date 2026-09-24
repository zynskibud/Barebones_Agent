use inventory::{add_item, out_of_stock, restock, sell, stock_value, Inventory, StockItem};

fn make_inventory() -> Inventory {
    let mut inventory = Inventory::new();
    add_item(&mut inventory, "A1", 2.5, 10).unwrap();
    add_item(&mut inventory, "B2", 10.0, 0).unwrap();
    inventory
}

#[test]
fn add_item_stores_price_and_quantity() {
    let inventory = make_inventory();
    let expected = StockItem {
        price: 2.5,
        quantity: 10,
    };
    assert_eq!(inventory["A1"], expected);
    assert_eq!(inventory["B2"].quantity, 0);
}

#[test]
fn add_item_rejects_duplicate_sku() {
    let mut inventory = make_inventory();
    assert!(add_item(&mut inventory, "A1", 3.0, 0).is_err());
}

#[test]
fn restock_and_sell() {
    let mut inventory = make_inventory();
    restock(&mut inventory, "B2", 5).unwrap();
    sell(&mut inventory, "B2", 2).unwrap();
    assert_eq!(inventory["B2"].quantity, 3);
}

#[test]
fn sell_rejects_too_many() {
    let mut inventory = make_inventory();
    assert!(sell(&mut inventory, "A1", 11).is_err());
}

#[test]
fn stock_value_adds_every_item() {
    assert_eq!(stock_value(&make_inventory()), 25.0);
}

#[test]
fn out_of_stock_lists_empty_items() {
    assert_eq!(out_of_stock(&make_inventory()), ["B2"]);
}
