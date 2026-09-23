from tickets import add_ticket, find_ticket, has_ticket, missing_tickets

IDS = [3, 8, 15, 21, 42, 57]


def test_find_ticket_in_the_middle():
    assert find_ticket(IDS, 21) == 3


def test_find_ticket_at_the_ends():
    assert find_ticket(IDS, 3) == 0
    assert find_ticket(IDS, 57) == 5


def test_find_ticket_missing_returns_minus_one():
    assert find_ticket(IDS, 20) == -1
    assert find_ticket(IDS, 100) == -1


def test_has_ticket():
    assert has_ticket(IDS, 8)
    assert not has_ticket(IDS, 9)


def test_missing_tickets():
    assert missing_tickets(IDS, [8, 9, 42, 43]) == [9, 43]


def test_add_ticket_keeps_the_list_sorted():
    ids = [3, 8, 15]
    add_ticket(ids, 10)
    add_ticket(ids, 8)
    assert ids == [3, 8, 10, 15]
