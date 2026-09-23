"""A restaurant menu.

A menu is a list of items. Each item is a dict with a name, a price,
and a course such as "starter", "main", or "dessert".
"""


def item_names(menu):
    """Return the item names in menu order."""
    return [item["name"] for item in menu]


def cheapest(menu):
    """Return the cheapest item. Return None if the menu is empty."""
    if not menu:
        return None
    best = menu[0]
    for item in menu[1:]:
        if item["price"] < best["price"]:
            best = item
    return best


def by_course(menu, course):
    """Return the items of one course, in menu order."""
    return [item for item in menu if item["course"] == course]


def under_price(menu, limit):
    """Return the items that cost `limit` or less, in menu order."""
    return [item for item in menu if item["price"] <= limit]


def format_item(item):
    """Return one line for the printed menu."""
    return f"{item['name']} - {item['price']:.2f}"


def format_menu(menu):
    """Return the whole menu as text, one item per line."""
    return "\n".join(format_item(item) for item in menu)
