"""Build a sitemap for a list of posts."""

import slugs
from posts import BASE_URL


def sitemap_lines(posts):
    """Return one URL per post, in post order."""
    lines = []
    for post in posts:
        slug = slugs.make_slug(post["title"])
        lines.append(f"{BASE_URL}/{slug}")
    return lines


def sitemap_text(posts):
    """Return the sitemap as text with one URL per line."""
    return "\n".join(sitemap_lines(posts)) + "\n"


def write_sitemap(posts, path):
    """Write the sitemap to a file."""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(sitemap_text(posts))
