"""A small shopping cart.

A cart is a list of items. Each item is a dict with a name, a price,
and a quantity.
"""


def make_cart():
    """Return a new, empty cart."""
    return []


def add_item(cart, name, price, quantity=1):
    """Add one line to the cart."""
    cart.append({"name": name, "price": price, "quantity": quantity})


def remove_item(cart, name):
    """Remove every line with the given name."""
    cart[:] = [item for item in cart if item["name"] != name]


def item_count(cart):
    """Return the number of units in the cart."""
    return sum(item["quantity"] for item in cart)


def cart_total(cart):
    """Return the price of the whole cart."""
    total = 0
    for item in cart:
        total += item["price"] * item["quantity"]
    return total
