from cart import add_item, item_count, make_cart, remove_item


def test_add_item_stores_the_fields():
    cart = make_cart()
    add_item(cart, "pen", 2, 3)
    assert cart == [{"name": "pen", "price": 2, "quantity": 3}]


def test_add_item_default_quantity_is_one():
    cart = make_cart()
    add_item(cart, "pad", 5)
    assert cart[0]["quantity"] == 1


def test_item_count_sums_the_quantities():
    cart = make_cart()
    add_item(cart, "pen", 2, 3)
    add_item(cart, "pad", 5)
    assert item_count(cart) == 4


def test_remove_item_drops_the_name():
    cart = make_cart()
    add_item(cart, "pen", 2, 3)
    add_item(cart, "pad", 5)
    remove_item(cart, "pen")
    assert [item["name"] for item in cart] == ["pad"]
