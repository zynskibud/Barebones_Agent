use std::fs;
use std::path::Path;
use std::ptr;

use blog::posts::{self, Post};
use blog::sitemap;
use blog::slugs::{is_slug, make_slug, unique_slugs};

fn make_posts() -> Vec<Post> {
    vec![
        Post::new("Hello, World!", "First post."),
        Post::new("Python 3.12 Notes", "Second post."),
    ]
}

fn read_source(name: &str) -> String {
    let path = Path::new(env!("CARGO_MANIFEST_DIR")).join("src").join(name);
    fs::read_to_string(&path)
        .unwrap_or_else(|error| panic!("cannot read {}: {error}", path.display()))
}

#[test]
fn make_slug_works() {
    assert_eq!(make_slug("Hello, World!"), "hello-world");
    assert_eq!(make_slug("  Two   Spaces "), "two-spaces");
    assert_eq!(make_slug("Python 3.12 Notes"), "python-3-12-notes");
}

#[test]
fn is_slug_still_works() {
    assert!(is_slug("hello-world"));
    assert!(!is_slug("Hello World"));
}

#[test]
fn unique_slugs_still_works() {
    assert_eq!(unique_slugs(&["A", "B", "a"]), ["a", "b", "a-2"]);
}

#[test]
fn post_url_still_works() {
    let posts = make_posts();
    assert_eq!(
        posts::post_url(&posts[0]),
        "https://example.com/posts/hello-world"
    );
}

#[test]
fn find_post_still_works() {
    let posts = make_posts();
    let found = posts::find_post(&posts, "python-3-12-notes").unwrap();
    assert!(ptr::eq(found, &posts[1]));
    assert!(posts::find_post(&posts, "missing").is_none());
}

#[test]
fn sitemap_still_works() {
    let expected = "https://example.com/posts/hello-world\n\
                    https://example.com/posts/python-3-12-notes\n";
    assert_eq!(sitemap::sitemap_text(&make_posts()), expected);
}

// Rust has no run-time check for a name in a module. This test reads the
// slugs module and the crate root instead: neither may define or re-export
// the old name.
#[test]
fn old_name_is_gone_from_the_module() {
    for name in ["slugs.rs", "lib.rs"] {
        let source = read_source(name);
        assert!(
            !source.contains("mk_slug"),
            "src/{name} still holds mk_slug"
        );
    }
}

#[test]
fn old_name_is_gone_from_every_source_file() {
    for name in ["slugs.rs", "posts.rs", "sitemap.rs"] {
        let source = read_source(name);
        assert!(
            !source.contains("mk_slug"),
            "src/{name} still holds mk_slug"
        );
    }
}
