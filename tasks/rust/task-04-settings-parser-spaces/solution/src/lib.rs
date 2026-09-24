//! Parse simple settings text.
//!
//! Each setting is one line in the form `key = value`.
//! Blank lines and lines that start with # are skipped.

use std::collections::BTreeMap;

/// The settings, from key to value.
pub type Settings = BTreeMap<String, String>;

/// Return a map with one entry for each setting line.
pub fn parse_settings(text: &str) -> Settings {
    let mut settings = Settings::new();
    for line in text.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let (key, value) = line.split_once('=').expect("bad setting line");
        settings.insert(key.trim().to_string(), value.trim().to_string());
    }
    settings
}

/// Return the setting as a number, or `default` if it is missing or not a number.
pub fn get_int(settings: &Settings, key: &str, default: i64) -> i64 {
    match settings.get(key) {
        Some(value) => value.parse().unwrap_or(default),
        None => default,
    }
}

/// Return true for true, yes, on, or 1. Return `default` if missing.
pub fn get_bool(settings: &Settings, key: &str, default: bool) -> bool {
    match settings.get(key) {
        Some(value) => matches!(value.to_lowercase().as_str(), "true" | "yes" | "on" | "1"),
        None => default,
    }
}

/// Return the settings as text, one `key = value` line each.
pub fn format_settings(settings: &Settings) -> String {
    let lines: Vec<String> = settings
        .iter()
        .map(|(key, value)| format!("{key} = {value}"))
        .collect();
    lines.join("\n")
}
