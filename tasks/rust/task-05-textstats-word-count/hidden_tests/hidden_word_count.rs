use textstats::{char_count, line_count, word_count};

#[test]
fn two_words() {
    assert_eq!(word_count("hello world"), 2);
}

#[test]
fn one_word() {
    assert_eq!(word_count("hello"), 1);
}

#[test]
fn empty_string_has_zero_words() {
    assert_eq!(word_count(""), 0);
}

#[test]
fn only_whitespace_has_zero_words() {
    assert_eq!(word_count("   \n\t "), 0);
}

#[test]
fn extra_spaces_and_newlines_do_not_add_words() {
    assert_eq!(word_count("  a  b\nc  "), 3);
}

#[test]
fn tabs_separate_words() {
    assert_eq!(word_count("a\tb\tc"), 3);
}

#[test]
fn punctuation_stays_inside_a_word() {
    assert_eq!(word_count("well, that is it."), 4);
}

#[test]
fn other_functions_still_work() {
    assert_eq!(char_count("abc"), 3);
    assert_eq!(line_count("a\n\nb\n"), 2);
}
