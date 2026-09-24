//! Simple statistics for a block of text.

use std::collections::HashMap;

/// The main counts for a text.
#[derive(Debug, Clone, PartialEq)]
pub struct Summary {
    pub chars: usize,
    pub lines: usize,
}

/// Return the number of characters, spaces included.
pub fn char_count(text: &str) -> usize {
    text.chars().count()
}

/// Return the number of lines that hold some text.
pub fn line_count(text: &str) -> usize {
    text.lines().filter(|line| !line.trim().is_empty()).count()
}

/// Return the longest line. Return an empty string if there is none.
pub fn longest_line(text: &str) -> &str {
    let mut longest = "";
    for line in text.lines() {
        if line.chars().count() > longest.chars().count() {
            longest = line;
        }
    }
    longest
}

/// Return the most common character that is not whitespace, or None.
/// If two characters tie, return the one that comes first in the text.
pub fn most_common_char(text: &str) -> Option<char> {
    let mut counts: HashMap<char, usize> = HashMap::new();
    for ch in text.chars() {
        if ch.is_whitespace() {
            continue;
        }
        *counts.entry(ch).or_insert(0) += 1;
    }
    let most = *counts.values().max()?;
    text.chars().find(|ch| counts.get(ch) == Some(&most))
}

/// Return the main counts in one value.
pub fn summary(text: &str) -> Summary {
    Summary {
        chars: char_count(text),
        lines: line_count(text),
    }
}
