"""Parse simple settings text.

Each setting is one line in the form `key = value`.
Blank lines and lines that start with # are skipped.
"""


def parse_settings(text):
    """Return a dict with one entry for each setting line."""
    settings = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        settings[key.strip()] = value.strip()
    return settings


def get_int(settings, key, default=0):
    """Return the setting as an int, or `default` if it is missing."""
    if key not in settings:
        return default
    return int(settings[key])


def get_bool(settings, key, default=False):
    """Return True for true, yes, on, or 1. Return `default` if missing."""
    if key not in settings:
        return default
    return settings[key].lower() in ("true", "yes", "on", "1")


def format_settings(settings):
    """Return the settings as text, one `key = value` line each."""
    lines = [f"{key} = {value}" for key, value in settings.items()]
    return "\n".join(lines)
