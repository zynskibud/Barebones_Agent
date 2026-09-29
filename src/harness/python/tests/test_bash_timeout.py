"""The bash_timeout config key: default 30 seconds, and a real value in the message.

Run: uv run python -m pytest src/harness/python/tests -q
"""

import json
import sys
import time
from pathlib import Path

import pytest

HARNESS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HARNESS))

from build import CONFIG_DIR  # noqa: E402
from env.local import LocalEnv  # noqa: E402
from tools import bash  # noqa: E402

MESSAGES = json.loads((CONFIG_DIR / "messages.json").read_text(encoding="utf-8"))


@pytest.fixture
def env(tmp_path):
    return LocalEnv(str(tmp_path))


class Spy(LocalEnv):
    """A LocalEnv that records the timeout it gets and raises a timeout."""

    def run(self, command, timeout):
        self.timeout = timeout
        from env.base import Timeout

        raise Timeout(command)


def test_absent_key_keeps_30_seconds_and_the_message(tmp_path):
    spy = Spy(str(tmp_path))
    result = bash.bash(spy, MESSAGES, {"command": "sleep 5"}, {})
    assert spy.timeout == 30
    assert result == "error: command timed out after 30 seconds"
    spy2 = Spy(str(tmp_path))
    assert bash.bash(spy2, MESSAGES, {"command": "x"}, {"bash_timeout": None}) == result
    assert spy2.timeout == 30


def test_bash_timeout_2_times_out_after_about_2_seconds(env):
    started = time.monotonic()
    result = bash.bash(env, MESSAGES, {"command": "sleep 5"}, {"bash_timeout": 2})
    elapsed = time.monotonic() - started
    assert 1.5 <= elapsed < 4.5
    assert result == "error: command timed out after 2 seconds"


def test_build_passes_bash_timeout_into_the_settings():
    from build import build_agent, load_config

    config = load_config(str(CONFIG_DIR / "baseline.yaml"))
    config.update({"env": "local", "tools": "files", "bash_timeout": 120})
    agent = build_agent(config, str(HARNESS))
    assert agent.tools.settings["bash_timeout"] == 120
