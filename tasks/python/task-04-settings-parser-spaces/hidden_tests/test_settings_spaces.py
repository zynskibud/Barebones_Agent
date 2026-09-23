from settings import get_bool, get_int, parse_settings


def test_one_space_each_side_still_works():
    assert parse_settings("port = 8080") == {"port": "8080"}


def test_extra_spaces_are_removed():
    assert parse_settings("port   =   8080") == {"port": "8080"}


def test_no_spaces_works():
    assert parse_settings("port=8080") == {"port": "8080"}


def test_spaces_on_one_side_only():
    assert parse_settings("host =localhost") == {"host": "localhost"}
    assert parse_settings("host= localhost") == {"host": "localhost"}


def test_inner_spaces_in_the_value_are_kept():
    assert parse_settings("name  =  my app") == {"name": "my app"}


def test_only_the_first_equals_sign_splits():
    assert parse_settings("url = http://x.test/?a=b") == {"url": "http://x.test/?a=b"}


def test_mixed_file():
    text = "# settings\nhost=localhost\nport   =   8080\n\ndebug = yes\n"
    assert parse_settings(text) == {
        "host": "localhost",
        "port": "8080",
        "debug": "yes",
    }


def test_comments_and_blank_lines_are_still_skipped():
    assert parse_settings("\n# a comment\n\n") == {}


def test_get_int_after_extra_spaces():
    assert get_int(parse_settings("port   =   8080"), "port") == 8080


def test_get_bool_after_no_spaces():
    assert get_bool(parse_settings("debug=true"), "debug") is True
