"""Turn titles into URL slugs.

A slug is lowercase. It holds only letters, digits, and single hyphens.
"""

import re


def make_slug(title):
    """Return the slug for a title."""
    lowered = title.lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", lowered)
    return cleaned.strip("-")


def is_slug(text):
    """Return True if the text is already a valid slug."""
    return text != "" and text == make_slug(text)


def unique_slugs(titles):
    """Return one slug per title. Add -2, -3, and so on to repeats."""
    seen = {}
    result = []
    for title in titles:
        slug = make_slug(title)
        count = seen.get(slug, 0) + 1
        seen[slug] = count
        if count > 1:
            slug = f"{slug}-{count}"
        result.append(slug)
    return result
