from settings import format_settings, get_bool, get_int, parse_settings

TEXT = """# server settings
host = localhost
port = 8080

debug = yes
"""


def test_parse_settings_reads_each_line():
    assert parse_settings(TEXT) == {
        "host": "localhost",
        "port": "8080",
        "debug": "yes",
    }


def test_parse_settings_skips_comments_and_blank_lines():
    assert parse_settings("# only a comment\n\n") == {}


def test_get_int():
    settings = parse_settings(TEXT)
    assert get_int(settings, "port") == 8080
    assert get_int(settings, "workers", 4) == 4


def test_get_bool():
    settings = parse_settings(TEXT)
    assert get_bool(settings, "debug") is True
    assert get_bool(settings, "verbose") is False


def test_format_settings_round_trip():
    settings = {"host": "localhost", "port": "8080"}
    assert parse_settings(format_settings(settings)) == settings
