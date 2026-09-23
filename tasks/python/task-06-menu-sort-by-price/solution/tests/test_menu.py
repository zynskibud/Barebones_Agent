from menu import by_course, cheapest, format_menu, item_names, under_price

MENU = [
    {"name": "Soup", "price": 4.5, "course": "starter"},
    {"name": "Steak", "price": 18.0, "course": "main"},
    {"name": "Pasta", "price": 11.0, "course": "main"},
    {"name": "Cake", "price": 6.0, "course": "dessert"},
]


def test_item_names():
    assert item_names(MENU) == ["Soup", "Steak", "Pasta", "Cake"]


def test_cheapest():
    assert cheapest(MENU)["name"] == "Soup"
    assert cheapest([]) is None


def test_by_course():
    assert item_names(by_course(MENU, "main")) == ["Steak", "Pasta"]


def test_under_price():
    assert item_names(under_price(MENU, 6.0)) == ["Soup", "Cake"]


def test_format_menu():
    assert format_menu(MENU[:2]) == "Soup - 4.50\nSteak - 18.00"
