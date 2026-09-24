use settings::{format_settings, get_bool, get_int, parse_settings, Settings};

const TEXT: &str = "# server settings
host = localhost
port = 8080

debug = yes
";

fn map(pairs: &[(&str, &str)]) -> Settings {
    pairs
        .iter()
        .map(|(key, value)| (key.to_string(), value.to_string()))
        .collect()
}

#[test]
fn parse_settings_reads_each_line() {
    let expected = map(&[("host", "localhost"), ("port", "8080"), ("debug", "yes")]);
    assert_eq!(parse_settings(TEXT), expected);
}

#[test]
fn parse_settings_skips_comments_and_blank_lines() {
    assert_eq!(parse_settings("# only a comment\n\n"), map(&[]));
}

#[test]
fn get_int_reads_a_number() {
    let settings = parse_settings(TEXT);
    assert_eq!(get_int(&settings, "port", 0), 8080);
    assert_eq!(get_int(&settings, "workers", 4), 4);
}

#[test]
fn get_bool_reads_a_flag() {
    let settings = parse_settings(TEXT);
    assert!(get_bool(&settings, "debug", false));
    assert!(!get_bool(&settings, "verbose", false));
}

#[test]
fn format_settings_round_trip() {
    let settings = map(&[("host", "localhost"), ("port", "8080")]);
    assert_eq!(parse_settings(&format_settings(&settings)), settings);
}
