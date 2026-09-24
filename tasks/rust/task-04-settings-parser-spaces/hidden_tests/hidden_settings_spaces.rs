use settings::{get_bool, get_int, parse_settings, Settings};

fn map(pairs: &[(&str, &str)]) -> Settings {
    pairs
        .iter()
        .map(|(key, value)| (key.to_string(), value.to_string()))
        .collect()
}

#[test]
fn one_space_each_side_still_works() {
    assert_eq!(parse_settings("port = 8080"), map(&[("port", "8080")]));
}

#[test]
fn extra_spaces_are_removed() {
    assert_eq!(parse_settings("port   =   8080"), map(&[("port", "8080")]));
}

#[test]
fn no_spaces_works() {
    assert_eq!(parse_settings("port=8080"), map(&[("port", "8080")]));
}

#[test]
fn spaces_on_one_side_only() {
    assert_eq!(
        parse_settings("host =localhost"),
        map(&[("host", "localhost")])
    );
    assert_eq!(
        parse_settings("host= localhost"),
        map(&[("host", "localhost")])
    );
}

#[test]
fn inner_spaces_in_the_value_are_kept() {
    assert_eq!(
        parse_settings("name  =  my app"),
        map(&[("name", "my app")])
    );
}

#[test]
fn only_the_first_equals_sign_splits() {
    assert_eq!(
        parse_settings("url = http://x.test/?a=b"),
        map(&[("url", "http://x.test/?a=b")])
    );
}

#[test]
fn mixed_file() {
    let text = "# settings\nhost=localhost\nport   =   8080\n\ndebug = yes\n";
    let expected = map(&[("host", "localhost"), ("port", "8080"), ("debug", "yes")]);
    assert_eq!(parse_settings(text), expected);
}

#[test]
fn comments_and_blank_lines_are_still_skipped() {
    assert_eq!(parse_settings("\n# a comment\n\n"), map(&[]));
}

#[test]
fn get_int_after_extra_spaces() {
    assert_eq!(get_int(&parse_settings("port   =   8080"), "port", 0), 8080);
}

#[test]
fn get_bool_after_no_spaces() {
    assert!(get_bool(&parse_settings("debug=true"), "debug", false));
}
