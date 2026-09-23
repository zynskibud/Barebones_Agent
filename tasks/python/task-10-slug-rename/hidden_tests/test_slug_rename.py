from pathlib import Path

import posts
import sitemap
import slugs
from slugs import is_slug, make_slug, unique_slugs

POSTS = [
    {"title": "Hello, World!", "body": "First post."},
    {"title": "Python 3.12 Notes", "body": "Second post."},
]


def test_make_slug():
    assert make_slug("Hello, World!") == "hello-world"
    assert make_slug("  Two   Spaces ") == "two-spaces"
    assert make_slug("Python 3.12 Notes") == "python-3-12-notes"


def test_is_slug_still_works():
    assert is_slug("hello-world")
    assert not is_slug("Hello World")


def test_unique_slugs_still_works():
    assert unique_slugs(["A", "B", "a"]) == ["a", "b", "a-2"]


def test_post_url_still_works():
    assert posts.post_url(POSTS[0]) == "https://example.com/posts/hello-world"


def test_find_post_still_works():
    assert posts.find_post(POSTS, "python-3-12-notes") is POSTS[1]
    assert posts.find_post(POSTS, "missing") is None


def test_sitemap_still_works():
    expected = (
        "https://example.com/posts/hello-world\n"
        "https://example.com/posts/python-3-12-notes\n"
    )
    assert sitemap.sitemap_text(POSTS) == expected


def test_old_name_is_gone_from_the_module():
    assert not hasattr(slugs, "mk_slug")


def test_old_name_is_gone_from_every_source_file():
    for module in (slugs, posts, sitemap):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "mk_slug" not in source, module.__file__
