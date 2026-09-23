import copy

from menu import cheapest, item_names, sort_by_price


def make_menu():
    return [
        {"name": "Steak", "price": 18.0, "course": "main"},
        {"name": "Soup", "price": 4.5, "course": "starter"},
        {"name": "Cake", "price": 6.0, "course": "dessert"},
        {"name": "Pasta", "price": 11.0, "course": "main"},
    ]


def test_orders_from_lowest_to_highest():
    assert item_names(sort_by_price(make_menu())) == ["Soup", "Cake", "Pasta", "Steak"]


def test_returns_the_same_item_dicts():
    menu = make_menu()
    result = sort_by_price(menu)
    assert result[0] is menu[1]
    assert result[-1] is menu[0]


def test_equal_prices_keep_their_original_order():
    menu = [
        {"name": "Tea", "price": 2.0, "course": "drink"},
        {"name": "Water", "price": 1.0, "course": "drink"},
        {"name": "Coffee", "price": 2.0, "course": "drink"},
        {"name": "Juice", "price": 2.0, "course": "drink"},
    ]
    assert item_names(sort_by_price(menu)) == ["Water", "Tea", "Coffee", "Juice"]


def test_input_list_does_not_change():
    menu = make_menu()
    before = copy.deepcopy(menu)
    sort_by_price(menu)
    assert menu == before


def test_returns_a_new_list():
    menu = make_menu()
    assert sort_by_price(menu) is not menu


def test_empty_menu():
    assert sort_by_price([]) == []


def test_single_item():
    menu = make_menu()[:1]
    assert sort_by_price(menu) == menu


def test_cheapest_still_works():
    assert cheapest(make_menu())["name"] == "Soup"
