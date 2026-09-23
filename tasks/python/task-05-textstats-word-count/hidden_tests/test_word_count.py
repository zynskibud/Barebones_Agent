from textstats import char_count, line_count, word_count


def test_two_words():
    assert word_count("hello world") == 2


def test_one_word():
    assert word_count("hello") == 1


def test_empty_string_has_zero_words():
    assert word_count("") == 0


def test_only_whitespace_has_zero_words():
    assert word_count("   \n\t ") == 0


def test_extra_spaces_and_newlines_do_not_add_words():
    assert word_count("  a  b\nc  ") == 3


def test_tabs_separate_words():
    assert word_count("a\tb\tc") == 3


def test_punctuation_stays_inside_a_word():
    assert word_count("well, that is it.") == 4


def test_other_functions_still_work():
    assert char_count("abc") == 3
    assert line_count("a\n\nb\n") == 2
