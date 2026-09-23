"""Track stock for a small shop.

The inventory is a dict. The key is the SKU. The value is a dict with
a price and a quantity.
"""


def add_item(inventory, sku, price, quantity=0):
    """Add a new item.

    Raise ValueError if the SKU already exists or the price is negative.
    """
    if sku in inventory:
        raise ValueError(f"duplicate sku: {sku}")
    if price < 0:
        raise ValueError(f"negative price: {price}")
    inventory[sku] = {"price": price, "quantity": quantity}


def restock(inventory, sku, amount):
    """Add `amount` units to an existing item."""
    inventory[sku]["quantity"] += amount


def sell(inventory, sku, amount):
    """Remove `amount` units. Raise ValueError if there is not enough stock."""
    item = inventory[sku]
    if amount > item["quantity"]:
        raise ValueError(f"not enough stock for {sku}")
    item["quantity"] -= amount


def stock_value(inventory):
    """Return the value of all stock at the current prices."""
    return sum(item["price"] * item["quantity"] for item in inventory.values())


def out_of_stock(inventory):
    """Return the SKUs with zero units, in insertion order."""
    return [sku for sku, item in inventory.items() if item["quantity"] == 0]
