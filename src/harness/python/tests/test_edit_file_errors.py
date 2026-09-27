"""Tests for the tool_errors setting (lever 1): plain vs. rich edit_file errors.

Run: uv run python -m pytest src/harness/python/tests -q

Every test runs edit_file through a LocalEnv on a temp folder. No model, no
Ollama, no Docker. Plain mode must stay byte-identical to config/messages.json.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
HARNESS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HARNESS_ROOT))

from env.local import LocalEnv  # noqa: E402
from tools.files import edit_file  # noqa: E402
from tools.registry import Tools  # noqa: E402

MESSAGES = json.loads((REPO_ROOT / "config" / "messages.json").read_text(encoding="utf-8"))
TOOLS_FILE = json.loads((REPO_ROOT / "config" / "tools.json").read_text(encoding="utf-8"))
EDIT_FILE_DEFINITION = TOOLS_FILE["tools"]["edit_file"]

CART_PY = 'def total(items):\n    return sum(item["price"] for item in items)\n\n'


def write_cart(tmp_path: Path) -> LocalEnv:
    (tmp_path / "cart.py").write_text(CART_PY, encoding="utf-8")
    return LocalEnv(str(tmp_path))


def test_plain_mode_returns_old_string_unchanged(tmp_path):
    """Plain mode returns exactly today's error string, from messages.json."""
    env = write_cart(tmp_path)
    arguments = {"path": "cart.py", "old_str": "not in the file", "new_str": "x"}
    result = edit_file(env, MESSAGES, arguments, {"tool_errors": "plain"})
    assert result == MESSAGES["errors"]["old_str_not_found"].format(path="cart.py")


def test_absent_tool_errors_behaves_like_plain(tmp_path):
    """An empty settings dict (tool_errors absent) means plain, same as explicit plain."""
    env = write_cart(tmp_path)
    arguments = {"path": "cart.py", "old_str": "not in the file", "new_str": "x"}
    result = edit_file(env, MESSAGES, arguments, {})
    assert result == MESSAGES["errors"]["old_str_not_found"].format(path="cart.py")


def test_rich_mode_appends_closest_matches(tmp_path):
    """Rich mode adds the plain string, a blank line, and up to 3 candidate regions."""
    env = write_cart(tmp_path)
    # Single-quote typo: does not match the file's double-quoted line, but is
    # the closest line in the file by difflib ratio.
    old = '    return sum(item[\'price\'] for item in items)'
    arguments = {"path": "cart.py", "old_str": old, "new_str": "x"}
    result = edit_file(env, MESSAGES, arguments, {"tool_errors": "rich"})
    base = MESSAGES["errors"]["old_str_not_found"].format(path="cart.py")
    expected = (
        f"{base}\n"
        "\n"
        "closest matches (line: text):\n"
        "1: def total(items):\n"
        '2:     return sum(item["price"] for item in items)\n'
        "3:"
    )
    assert result == expected


def test_rich_mode_multiple_matches_lists_lines(tmp_path):
    """Rich mode lists the 1-based line numbers of every match, up to 5."""
    content = "x = 1\ny = 2\nx = 1\nz = 3\n"
    (tmp_path / "values.py").write_text(content, encoding="utf-8")
    env = LocalEnv(str(tmp_path))
    arguments = {"path": "values.py", "old_str": "x = 1\n", "new_str": "x = 2\n"}
    result = edit_file(env, MESSAGES, arguments, {"tool_errors": "rich"})
    base = MESSAGES["errors"]["old_str_multiple"].format(path="values.py")
    assert result == f"{base}\nmatches at lines: 1, 3"


def test_rich_mode_short_file_does_not_crash(tmp_path):
    """A file with fewer than 3 lines, or no lines, still returns a valid result."""
    (tmp_path / "one_line.py").write_text("x = 1", encoding="utf-8")
    env = LocalEnv(str(tmp_path))
    arguments = {"path": "one_line.py", "old_str": "not here", "new_str": "y"}
    result = edit_file(env, MESSAGES, arguments, {"tool_errors": "rich"})
    base = MESSAGES["errors"]["old_str_not_found"].format(path="one_line.py")
    assert result.startswith(base)
    assert "closest matches (line: text):" in result
    assert "1: x = 1" in result

    (tmp_path / "empty.py").write_text("", encoding="utf-8")
    arguments = {"path": "empty.py", "old_str": "not here", "new_str": "y"}
    result = edit_file(env, MESSAGES, arguments, {"tool_errors": "rich"})
    # No lines in the file means no candidates: rich falls back to the plain string.
    assert result == MESSAGES["errors"]["old_str_not_found"].format(path="empty.py")


def test_rich_result_over_10000_characters_is_truncated(tmp_path):
    """A rich result over MAX_RESULT_CHARS is truncated the same way as any other result."""
    long_line = "y" * 20_000
    content = f"{long_line}\n"
    (tmp_path / "big.py").write_text(content, encoding="utf-8")
    env = LocalEnv(str(tmp_path))
    definitions = [EDIT_FILE_DEFINITION]
    handlers = {"edit_file": edit_file}
    tools = Tools(definitions, handlers, env, MESSAGES, {"tool_errors": "rich"})
    result, malformed = tools.call("edit_file", {"path": "big.py", "old_str": "not here", "new_str": "z"})
    assert not malformed
    base = MESSAGES["errors"]["old_str_not_found"].format(path="big.py")
    full = base + "\n\nclosest matches (line: text):\n1: " + long_line
    cut = len(full) - 10_000
    expected = full[:10_000] + "\n" + MESSAGES["truncated"].format(n=cut)
    assert result == expected
