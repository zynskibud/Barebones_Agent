import pytest

from inventory import add_item, sell, stock_value


def test_negative_price_raises_value_error():
    inventory = {}
    with pytest.raises(ValueError):
        add_item(inventory, "A1", -1.0, 5)


def test_small_negative_float_raises_value_error():
    inventory = {}
    with pytest.raises(ValueError):
        add_item(inventory, "A1", -0.01)


def test_negative_price_does_not_add_the_item():
    inventory = {}
    try:
        add_item(inventory, "A1", -5, 2)
    except ValueError:
        pass
    assert "A1" not in inventory


def test_zero_price_is_allowed():
    inventory = {}
    add_item(inventory, "FREE", 0, 3)
    assert inventory["FREE"] == {"price": 0, "quantity": 3}


def test_positive_price_is_allowed():
    inventory = {}
    add_item(inventory, "A1", 2.5, 10)
    assert inventory["A1"] == {"price": 2.5, "quantity": 10}


def test_duplicate_sku_still_raises_value_error():
    inventory = {}
    add_item(inventory, "A1", 2.5)
    with pytest.raises(ValueError):
        add_item(inventory, "A1", 3.0)


def test_other_functions_still_work():
    inventory = {}
    add_item(inventory, "A1", 2.0, 4)
    sell(inventory, "A1", 1)
    assert stock_value(inventory) == 6.0
