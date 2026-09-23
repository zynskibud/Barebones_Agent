import pytest

from inventory import add_item, out_of_stock, restock, sell, stock_value


def make_inventory():
    inventory = {}
    add_item(inventory, "A1", 2.5, 10)
    add_item(inventory, "B2", 10.0)
    return inventory


def test_add_item_stores_price_and_quantity():
    inventory = make_inventory()
    assert inventory["A1"] == {"price": 2.5, "quantity": 10}
    assert inventory["B2"]["quantity"] == 0


def test_add_item_rejects_duplicate_sku():
    inventory = make_inventory()
    with pytest.raises(ValueError):
        add_item(inventory, "A1", 3.0)


def test_restock_and_sell():
    inventory = make_inventory()
    restock(inventory, "B2", 5)
    sell(inventory, "B2", 2)
    assert inventory["B2"]["quantity"] == 3


def test_sell_rejects_too_many():
    inventory = make_inventory()
    with pytest.raises(ValueError):
        sell(inventory, "A1", 11)


def test_stock_value():
    assert stock_value(make_inventory()) == 25.0


def test_out_of_stock():
    assert out_of_stock(make_inventory()) == ["B2"]
