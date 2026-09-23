"""Blog posts.

A post is a dict with a title and a body.
"""

from slugs import mk_slug

BASE_URL = "https://example.com/posts"


def post_url(post):
    """Return the public URL of a post."""
    return f"{BASE_URL}/{mk_slug(post['title'])}"


def find_post(posts, slug):
    """Return the post whose title gives this slug, or None."""
    for post in posts:
        if mk_slug(post["title"]) == slug:
            return post
    return None


def post_summary(post, length=40):
    """Return the first `length` characters of the body."""
    body = post["body"]
    if len(body) <= length:
        return body
    return body[:length] + "..."
