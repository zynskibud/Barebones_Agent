//! A restaurant menu.
//!
//! A menu is a list of items. Each item has a name, a price, and a course
//! such as "starter", "main", or "dessert".

/// One dish on the menu.
#[derive(Debug, Clone, PartialEq)]
pub struct MenuItem {
    pub name: String,
    pub price: f64,
    pub course: String,
}

impl MenuItem {
    /// Return a new menu item.
    pub fn new(name: &str, price: f64, course: &str) -> MenuItem {
        MenuItem {
            name: name.to_string(),
            price,
            course: course.to_string(),
        }
    }
}

/// Return the item names in the order given.
pub fn item_names<'a>(items: impl IntoIterator<Item = &'a MenuItem>) -> Vec<&'a str> {
    items.into_iter().map(|item| item.name.as_str()).collect()
}

/// Return the cheapest item. Return None if the menu is empty.
pub fn cheapest(menu: &[MenuItem]) -> Option<&MenuItem> {
    let mut best = menu.first()?;
    for item in &menu[1..] {
        if item.price < best.price {
            best = item;
        }
    }
    Some(best)
}

/// Return the items of one course, in menu order.
pub fn by_course<'a>(menu: &'a [MenuItem], course: &str) -> Vec<&'a MenuItem> {
    menu.iter().filter(|item| item.course == course).collect()
}

/// Return the items that cost `limit` or less, in menu order.
pub fn under_price(menu: &[MenuItem], limit: f64) -> Vec<&MenuItem> {
    menu.iter().filter(|item| item.price <= limit).collect()
}

/// Return one line for the printed menu.
pub fn format_item(item: &MenuItem) -> String {
    format!("{} - {:.2}", item.name, item.price)
}

/// Return the whole menu as text, one item per line.
pub fn format_menu(menu: &[MenuItem]) -> String {
    let lines: Vec<String> = menu.iter().map(format_item).collect();
    lines.join("\n")
}
