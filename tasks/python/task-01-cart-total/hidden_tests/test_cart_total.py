import pytest

from cart import add_item, cart_total, item_count, make_cart


def test_total_multiplies_price_by_quantity():
    cart = make_cart()
    add_item(cart, "pen", 2, 3)
    assert cart_total(cart) == 6


def test_total_adds_several_lines():
    cart = make_cart()
    add_item(cart, "pen", 2, 3)
    add_item(cart, "pad", 5, 2)
    add_item(cart, "ink", 10)
    assert cart_total(cart) == 26


def test_total_with_quantity_one_is_the_price():
    cart = make_cart()
    add_item(cart, "ink", 10)
    assert cart_total(cart) == 10


def test_total_of_empty_cart_is_zero():
    assert cart_total(make_cart()) == 0


def test_total_with_float_prices():
    cart = make_cart()
    add_item(cart, "tape", 1.5, 4)
    add_item(cart, "glue", 0.25, 2)
    assert cart_total(cart) == pytest.approx(6.5)


def test_item_count_still_works():
    cart = make_cart()
    add_item(cart, "pen", 2, 3)
    add_item(cart, "pad", 5, 2)
    assert item_count(cart) == 5
