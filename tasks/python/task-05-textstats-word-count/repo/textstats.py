"""Simple statistics for a block of text."""


def char_count(text):
    """Return the number of characters, spaces included."""
    return len(text)


def line_count(text):
    """Return the number of lines that hold some text."""
    return sum(1 for line in text.splitlines() if line.strip())


def longest_line(text):
    """Return the longest line. Return an empty string if there is none."""
    longest = ""
    for line in text.splitlines():
        if len(line) > len(longest):
            longest = line
    return longest


def most_common_char(text):
    """Return the most common non-space character, or None."""
    counts = {}
    for char in text:
        if char.isspace():
            continue
        counts[char] = counts.get(char, 0) + 1
    if not counts:
        return None
    return max(counts, key=counts.get)


def summary(text):
    """Return the main counts in one dict."""
    return {
        "chars": char_count(text),
        "lines": line_count(text),
    }
