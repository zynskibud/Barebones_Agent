"""Tests for the auto_check config key: the harness runs a check after edit_file.

Run: uv run python -m pytest src/harness/python/tests -q

These tests call the file tool functions directly, on a LocalEnv in a tmp_path
folder. No model, no Ollama, no Docker.
"""

import json
import sys
from pathlib import Path

import pytest

# The harness modules import each other as top-level modules, as they do when run as scripts.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from env.local import LocalEnv  # noqa: E402
from tools import files  # noqa: E402
from tools.registry import Tools  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[4]
MESSAGES = json.loads((REPO_ROOT / "config" / "messages.json").read_text(encoding="utf-8"))


@pytest.fixture
def env(tmp_path):
    return LocalEnv(str(tmp_path))


def test_auto_check_off_returns_exactly_the_ok_line(env, tmp_path):
    (tmp_path / "a.py").write_text("old\n", encoding="utf-8")
    result = files.edit_file(env, MESSAGES, {"path": "a.py", "old_str": "old\n", "new_str": "new\n"}, {})
    assert result == "ok: edited a.py"


def test_auto_check_on_runs_the_command_and_shows_its_output(env, tmp_path):
    (tmp_path / "a.py").write_text("old\n", encoding="utf-8")
    result = files.edit_file(
        env,
        MESSAGES,
        {"path": "a.py", "old_str": "old\n", "new_str": "new\n"},
        {"auto_check": "echo checked; exit 0"},
    )
    lines = result.split("\n")
    assert lines[0] == "ok: edited a.py"
    assert lines[1] == ""
    assert lines[2] == "check: echo checked; exit 0"
    assert "checked" in result
    assert result.rstrip().endswith("exit code: 0")


def test_auto_check_on_a_failing_command_shows_stderr_and_the_exit_code(env, tmp_path):
    (tmp_path / "a.py").write_text("old\n", encoding="utf-8")
    result = files.edit_file(
        env,
        MESSAGES,
        {"path": "a.py", "old_str": "old\n", "new_str": "new\n"},
        {"auto_check": "echo boom 1>&2; exit 1"},
    )
    assert "boom" in result
    assert result.rstrip().endswith("exit code: 1")


def test_auto_check_on_a_timeout_gives_the_timeout_error(env, tmp_path, monkeypatch):
    (tmp_path / "a.py").write_text("old\n", encoding="utf-8")
    # A tiny timeout, so the test does not wait for the real 30-second limit.
    monkeypatch.setattr(files, "TIMEOUT_SECONDS", 0.05)
    result = files.edit_file(
        env,
        MESSAGES,
        {"path": "a.py", "old_str": "old\n", "new_str": "new\n"},
        {"auto_check": "sleep 1"},
    )
    assert result.endswith(MESSAGES["errors"]["timeout"])


def test_auto_check_never_runs_after_a_failed_edit(env, tmp_path):
    (tmp_path / "a.py").write_text("old\n", encoding="utf-8")
    result = files.edit_file(
        env,
        MESSAGES,
        {"path": "a.py", "old_str": "missing", "new_str": "new\n"},
        {"auto_check": "echo should not run"},
    )
    assert result == MESSAGES["errors"]["old_str_not_found"].format(path="a.py")
    assert "should not run" not in result


def test_auto_check_runs_after_a_create(env, tmp_path):
    result = files.edit_file(
        env,
        MESSAGES,
        {"path": "new.py", "old_str": "", "new_str": "x = 1\n"},
        {"auto_check": "echo checked; exit 0"},
    )
    assert result.startswith("ok: created new.py")
    assert "checked" in result
    assert result.rstrip().endswith("exit code: 0")


def test_build_agent_wires_auto_check_into_the_edit_file_tool(env, tmp_path):
    """The same wiring build.py does: pass auto_check through the settings dict."""
    (tmp_path / "a.py").write_text("old\n", encoding="utf-8")
    handlers = {"edit_file": files.edit_file}
    definitions = [
        {
            "type": "function",
            "function": {
                "name": "edit_file",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}, "old_str": {"type": "string"}, "new_str": {"type": "string"}},
                    "required": ["path", "old_str", "new_str"],
                },
            },
        }
    ]
    tools = Tools(definitions, handlers, env, MESSAGES, {"auto_check": "echo checked; exit 0"})
    content, malformed = tools.call("edit_file", {"path": "a.py", "old_str": "old\n", "new_str": "new\n"})
    assert malformed is False
    assert content.startswith("ok: edited a.py")
    assert "checked" in content
