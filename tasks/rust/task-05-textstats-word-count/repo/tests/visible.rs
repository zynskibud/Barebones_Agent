use textstats::{char_count, line_count, longest_line, most_common_char, summary, Summary};

const TEXT: &str = "one two\n\nthree four five\n";

#[test]
fn char_count_counts_every_character() {
    assert_eq!(char_count("abc"), 3);
    assert_eq!(char_count(""), 0);
}

#[test]
fn line_count_ignores_blank_lines() {
    assert_eq!(line_count(TEXT), 2);
}

#[test]
fn longest_line_picks_the_longest() {
    assert_eq!(longest_line(TEXT), "three four five");
    assert_eq!(longest_line(""), "");
}

#[test]
fn most_common_char_skips_whitespace() {
    assert_eq!(most_common_char("aab b"), Some('a'));
    assert_eq!(most_common_char("   "), None);
}

#[test]
fn summary_holds_the_counts() {
    assert_eq!(
        summary(TEXT),
        Summary {
            chars: 25,
            lines: 2
        }
    );
}
