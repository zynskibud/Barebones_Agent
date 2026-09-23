from textstats import char_count, line_count, longest_line, most_common_char, summary

TEXT = "one two\n\nthree four five\n"


def test_char_count():
    assert char_count("abc") == 3
    assert char_count("") == 0


def test_line_count_ignores_blank_lines():
    assert line_count(TEXT) == 2


def test_longest_line():
    assert longest_line(TEXT) == "three four five"
    assert longest_line("") == ""


def test_most_common_char():
    assert most_common_char("aab b") == "a"
    assert most_common_char("   ") is None


def test_summary():
    assert summary(TEXT) == {"chars": 25, "lines": 2}
