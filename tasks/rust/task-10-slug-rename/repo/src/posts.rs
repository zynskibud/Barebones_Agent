//! Blog posts.
//!
//! A post has a title and a body.

use crate::slugs::mk_slug;

pub const BASE_URL: &str = "https://example.com/posts";

/// One blog post.
#[derive(Debug, Clone, PartialEq)]
pub struct Post {
    pub title: String,
    pub body: String,
}

impl Post {
    /// Return a new post.
    pub fn new(title: &str, body: &str) -> Post {
        Post {
            title: title.to_string(),
            body: body.to_string(),
        }
    }
}

/// Return the public URL of a post.
pub fn post_url(post: &Post) -> String {
    format!("{BASE_URL}/{}", mk_slug(&post.title))
}

/// Return the post whose title gives this slug, or None.
pub fn find_post<'a>(posts: &'a [Post], slug: &str) -> Option<&'a Post> {
    for post in posts {
        if mk_slug(&post.title) == slug {
            return Some(post);
        }
    }
    None
}

/// Return the first `length` characters of the body.
pub fn post_summary(post: &Post, length: usize) -> String {
    if post.body.chars().count() <= length {
        return post.body.clone();
    }
    let start: String = post.body.chars().take(length).collect();
    start + "..."
}
