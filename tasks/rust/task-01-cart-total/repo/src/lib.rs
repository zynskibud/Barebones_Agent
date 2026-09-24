//! A small shopping cart.
//!
//! A cart is a list of items. Each item has a name, a price, and a quantity.

/// One line in the cart.
#[derive(Debug, Clone, PartialEq)]
pub struct Item {
    pub name: String,
    pub price: f64,
    pub quantity: u32,
}

/// Return a new, empty cart.
pub fn make_cart() -> Vec<Item> {
    Vec::new()
}

/// Add one line to the cart.
pub fn add_item(cart: &mut Vec<Item>, name: &str, price: f64, quantity: u32) {
    cart.push(Item {
        name: name.to_string(),
        price,
        quantity,
    });
}

/// Remove every line with the given name.
pub fn remove_item(cart: &mut Vec<Item>, name: &str) {
    cart.retain(|item| item.name != name);
}

/// Return the number of units in the cart.
pub fn item_count(cart: &[Item]) -> u32 {
    cart.iter().map(|item| item.quantity).sum()
}

/// Return the price of the whole cart.
pub fn cart_total(cart: &[Item]) -> f64 {
    let mut total = 0.0;
    for item in cart {
        total += item.price;
    }
    total
}
