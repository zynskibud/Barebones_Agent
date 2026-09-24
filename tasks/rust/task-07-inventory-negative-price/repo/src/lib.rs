//! Track stock for a small shop.
//!
//! The inventory maps each SKU to a stock item with a price and a quantity.

use std::collections::BTreeMap;

/// The price and the number of units for one SKU.
#[derive(Debug, Clone, PartialEq)]
pub struct StockItem {
    pub price: f64,
    pub quantity: u32,
}

/// The stock, from SKU to item.
pub type Inventory = BTreeMap<String, StockItem>;

/// Add a new item. Return an error if the SKU already exists.
pub fn add_item(
    inventory: &mut Inventory,
    sku: &str,
    price: f64,
    quantity: u32,
) -> Result<(), String> {
    if inventory.contains_key(sku) {
        return Err(format!("duplicate sku: {sku}"));
    }
    inventory.insert(sku.to_string(), StockItem { price, quantity });
    Ok(())
}

/// Add `amount` units to an existing item.
pub fn restock(inventory: &mut Inventory, sku: &str, amount: u32) -> Result<(), String> {
    let item = inventory
        .get_mut(sku)
        .ok_or(format!("unknown sku: {sku}"))?;
    item.quantity += amount;
    Ok(())
}

/// Remove `amount` units. Return an error if there is not enough stock.
pub fn sell(inventory: &mut Inventory, sku: &str, amount: u32) -> Result<(), String> {
    let item = inventory
        .get_mut(sku)
        .ok_or(format!("unknown sku: {sku}"))?;
    if amount > item.quantity {
        return Err(format!("not enough stock for {sku}"));
    }
    item.quantity -= amount;
    Ok(())
}

/// Return the value of all stock at the current prices.
pub fn stock_value(inventory: &Inventory) -> f64 {
    inventory
        .values()
        .map(|item| item.price * item.quantity as f64)
        .sum()
}

/// Return the SKUs with zero units, in SKU order.
pub fn out_of_stock(inventory: &Inventory) -> Vec<&str> {
    inventory
        .iter()
        .filter(|(_, item)| item.quantity == 0)
        .map(|(sku, _)| sku.as_str())
        .collect()
}
