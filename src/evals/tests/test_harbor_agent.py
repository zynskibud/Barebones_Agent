"""Tests for the Harbor agent adapter, with a fake model and a fake Harbor environment.

Run: uv run python -m pytest src/evals -q
"""

import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
EVALS = Path(__file__).resolve().parents[1]

# Other eval tests put src/evals on sys.path, where src/evals/harbor would hide
# the installed harbor package. Import the real package without that entry first.
saved = list(sys.path)
sys.path[:] = [entry for entry in sys.path if Path(entry or ".").resolve() != EVALS]
sys.modules.pop("harbor", None)
import harbor.agents.base  # noqa: E402,F401

sys.path[:] = saved
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src" / "harness" / "python" / "tests"))

import build  # noqa: E402
from fake_harbor import FakeEnvironment  # noqa: E402
from harbor.models.agent.context import AgentContext  # noqa: E402

from src.evals.harbor import agent as adapter  # noqa: E402

SPEC_KEYS = [
    "config_id", "task", "trial", "stop_reason", "turns", "seconds", "prompt_tokens", "completion_tokens",
    "model", "model_digest", "num_ctx", "temperature", "think", "exit_code", "tool_calls",
    "malformed_tool_calls", "passed", "grader_output",
]


class FakeModel:
    """A model that answers once with no tool calls."""

    def __init__(self, **settings) -> None:
        self.settings = settings

    def chat(self, messages, definitions, timeout=None):
        return {"message": {"role": "assistant", "content": "done"}, "prompt_eval_count": 7, "eval_count": 2}

    def digest(self):
        return "fake-digest"

    def loaded_context_length(self):
        return 4096

    def default_parameters(self):
        return {"temperature": "0.6"}


def test_harbor_config_applies_overrides():
    config = adapter.harbor_config("prompt=config/system_prompt_v2.txt, think=true,max_turns=5")
    assert config["env"] == "harbor"
    assert config["prompt"] == "config/system_prompt_v2.txt"
    assert config["think"] is True
    assert config["max_turns"] == 5


def test_task_name_from_session():
    assert adapter.task_name("fix-git__AbC1234__agent", Path("x/agent")) == "fix-git"
    assert adapter.task_name(None, Path("jobs/j/fix-git__AbC1234/agent")) == "fix-git"


def test_run_writes_transcript_and_result(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "Model", FakeModel)
    monkeypatch.setenv("HARBOR_SET", "prompt=config/system_prompt_v2.txt")
    root = tmp_path / "container" / "app"
    root.mkdir(parents=True)
    logs = tmp_path / "trial" / "agent"
    agent = adapter.BarebonesAgent(logs_dir=logs)
    agent.session_id = "fix-git__AbC1234__agent"
    context = AgentContext()
    environment = FakeEnvironment(root, workdir=str(root))
    asyncio.run(agent.run("Fix the repo.", environment, context))

    result = json.loads((logs / "result.json").read_text())
    assert list(result) == SPEC_KEYS
    assert result["task"] == "fix-git"
    assert result["stop_reason"] == "end_turn"
    assert result["turns"] == 1
    assert result["config_id"] == "py.files-bash.harbor.terminal-bench-2-1.qwen3-8b.no-think"
    lines = [json.loads(line) for line in (logs / "transcript.jsonl").read_text().splitlines()]
    assert [line["type"] for line in lines] == ["config", "system", "user", "assistant", "end"]
    assert lines[2]["content"] == "Fix the repo."
    assert lines[1]["content"] == (REPO_ROOT / "config" / "system_prompt_v2.txt").read_text().rstrip()
    assert context.n_input_tokens == 7 and context.n_output_tokens == 2
