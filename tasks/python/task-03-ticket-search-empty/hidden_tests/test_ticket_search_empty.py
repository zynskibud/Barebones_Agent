from tickets import add_ticket, find_ticket, has_ticket, missing_tickets

IDS = [3, 8, 15, 21, 42, 57]


def test_empty_list_returns_minus_one():
    assert find_ticket([], 5) == -1


def test_has_ticket_on_empty_list_is_false():
    assert not has_ticket([], 5)


def test_missing_tickets_on_empty_list_returns_all_wanted():
    assert missing_tickets([], [1, 2, 3]) == [1, 2, 3]


def test_add_ticket_to_empty_list():
    ids = []
    add_ticket(ids, 7)
    assert ids == [7]


def test_single_item_list():
    assert find_ticket([9], 9) == 0
    assert find_ticket([9], 4) == -1
    assert find_ticket([9], 12) == -1


def test_find_ticket_still_finds_every_item():
    for index, ticket_id in enumerate(IDS):
        assert find_ticket(IDS, ticket_id) == index


def test_find_ticket_still_returns_minus_one_when_missing():
    assert find_ticket(IDS, 1) == -1
    assert find_ticket(IDS, 20) == -1
    assert find_ticket(IDS, 99) == -1
