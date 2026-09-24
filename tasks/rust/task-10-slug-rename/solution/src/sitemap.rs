//! Build a sitemap for a list of posts.

use std::fs;
use std::io;
use std::path::Path;

use crate::posts::{Post, BASE_URL};
use crate::slugs;

/// Return one URL per post, in post order.
pub fn sitemap_lines(posts: &[Post]) -> Vec<String> {
    let mut lines = Vec::new();
    for post in posts {
        let slug = slugs::make_slug(&post.title);
        lines.push(format!("{BASE_URL}/{slug}"));
    }
    lines
}

/// Return the sitemap as text with one URL per line.
pub fn sitemap_text(posts: &[Post]) -> String {
    sitemap_lines(posts).join("\n") + "\n"
}

/// Write the sitemap to a file.
pub fn write_sitemap(posts: &[Post], path: &Path) -> io::Result<()> {
    fs::write(path, sitemap_text(posts))
}
