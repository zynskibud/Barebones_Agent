//! Turn titles into URL slugs.
//!
//! A slug is lowercase. It holds only letters, digits, and single hyphens.

use std::collections::HashMap;

/// Return the slug for a title.
pub fn make_slug(title: &str) -> String {
    let mut slug = String::new();
    for ch in title.to_lowercase().chars() {
        if ch.is_ascii_lowercase() || ch.is_ascii_digit() {
            slug.push(ch);
        } else if !slug.ends_with('-') {
            slug.push('-');
        }
    }
    slug.trim_matches('-').to_string()
}

/// Return true if the text is already a valid slug.
pub fn is_slug(text: &str) -> bool {
    !text.is_empty() && text == make_slug(text)
}

/// Return one slug per title. Add -2, -3, and so on to repeats.
pub fn unique_slugs(titles: &[&str]) -> Vec<String> {
    let mut seen: HashMap<String, u32> = HashMap::new();
    let mut result = Vec::new();
    for title in titles {
        let slug = make_slug(title);
        let count = seen.entry(slug.clone()).or_insert(0);
        *count += 1;
        if *count > 1 {
            result.push(format!("{slug}-{count}"));
        } else {
            result.push(slug);
        }
    }
    result
}
