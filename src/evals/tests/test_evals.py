"""Tests for the eval harness.

Run: uv run python -m pytest src/evals -q

The end-to-end tests start a small fake harness program instead of the real one.
The fake harness follows the flags, the transcript format, and result.json in docs/harness-spec.md.
"""

import json
import sys
import time
from pathlib import Path

import pytest
import yaml

# The eval modules import each other as top-level modules, as they do when run as scripts.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import grade  # noqa: E402
import report  # noqa: E402
import run  # noqa: E402
import suite  # noqa: E402

BASELINE_ID = "py.files-bash.local.python.qwen3-8b.no-think"

BUGGY = "def total(items):\n    return sum(price for price, qty in items)\n"
FIXED = "def total(items):\n    return sum(price * qty for price, qty in items)\n"
HIDDEN_TEST = (
    "from cart import total\n\n\n"
    "def test_total():\n"
    "    assert total([(2.0, 3), (1.0, 1)]) == 7.0\n"
)

FAKE_HARNESS = r'''
import argparse, json, os, pathlib, sys, time

parser = argparse.ArgumentParser()
for flag in ("--config", "--workdir", "--mode", "--prompt-file", "--transcript", "--result"):
    parser.add_argument(flag)
args = parser.parse_args()
behavior = os.environ["FAKE_HARNESS"]
work = pathlib.Path(args.workdir)
if (work / "hidden_tests").exists() or (work / "solution").exists():
    sys.exit(4)
if behavior == "crash":
    print("boom", file=sys.stderr)
    sys.exit(3)
if behavior == "hang":
    time.sleep(30)
    sys.exit(0)
(work / "cart.py").write_text(FIXED)
path = "../hidden_tests/test_cart.py" if behavior == "cheat" else "cart.py"
records = [
    {"type": "config", "config_id": "x", "config": {}},
    {"type": "user", "content": pathlib.Path(args.prompt_file).read_text()},
    {"type": "assistant", "content": "", "tool_calls": [
        {"id": "call_0_0", "name": "read_file", "arguments": {"path": path}}]},
    {"type": "tool_result", "tool_call_id": "call_0_0", "name": "read_file", "content": "ok"},
    {"type": "end", "stop_reason": "end_turn", "turns": 1, "seconds": 0.5},
]
pathlib.Path(args.transcript).write_text("".join(json.dumps(r) + "\n" for r in records))
result = {
    "config_id": "x", "task": None, "trial": None, "stop_reason": "end_turn", "turns": 1,
    "seconds": 0.5, "prompt_tokens": 100, "completion_tokens": 10, "model": "qwen3:8b",
    "model_digest": "sha256:0", "num_ctx": 4096, "temperature": 0.6, "think": False,
    "exit_code": 0, "tool_calls": 1, "malformed_tool_calls": 0, "passed": None,
    "grader_output": None,
}
pathlib.Path(args.result).write_text(json.dumps(result))
print("stop_reason=end_turn turns=1 seconds=0.5")
'''.replace("FIXED", repr(FIXED))


def load_grid_and_baseline() -> tuple[dict, dict]:
    grid = run.load_yaml(run.CONFIG_DIR / "grid.yaml")
    baseline = run.load_yaml(run.CONFIG_DIR / "baseline.yaml")
    return grid, baseline


def make_task(tasks_root: Path, name: str = "task-01-cart", limits: dict | None = None, solution: str = FIXED) -> Path:
    """Write a small Python task with the four parts."""
    task_dir = tasks_root / "python" / name
    for part in ("repo", "solution", "hidden_tests"):
        (task_dir / part).mkdir(parents=True)
    (task_dir / "repo" / "cart.py").write_text(BUGGY)
    (task_dir / "solution" / "cart.py").write_text(solution)
    (task_dir / "hidden_tests" / "test_cart.py").write_text(HIDDEN_TEST)
    task = {
        "name": "cart",
        "type": "bug-fix",
        "prompt": "The cart total ignores the quantity. Fix it.",
        "test_command": "python -m pytest hidden_tests -q",
        "limits": limits or {"max_turns": 40, "max_seconds": 600},
    }
    (task_dir / "task.yaml").write_text(yaml.safe_dump(task, sort_keys=False))
    return task_dir


@pytest.fixture
def fake_run(tmp_path, monkeypatch):
    """Point HARNESS_COMMANDS at the fake harness. Return a function that runs one suite."""
    script = tmp_path / "fake_harness.py"
    script.write_text(FAKE_HARNESS)
    monkeypatch.setitem(suite.HARNESS_COMMANDS, "py", [sys.executable, str(script)])
    _, baseline = load_grid_and_baseline()
    runs_dir = tmp_path / "runs"

    def go(behavior: str, trials: int = 1, **task_args) -> list[dict]:
        monkeypatch.setenv("FAKE_HARNESS", behavior)
        make_task(tmp_path / "tasks", **task_args)
        config = run.build_config(baseline, run.baseline_values(baseline))
        config_path = run.write_config(runs_dir, BASELINE_ID, config)
        return suite.run_suite(
            BASELINE_ID, config, config_path,
            runs_dir=runs_dir, tasks_root=tmp_path / "tasks", trials=trials,
        )

    return go


# Configuration IDs and stages


def test_config_id_baseline():
    _, baseline = load_grid_and_baseline()
    assert run.config_id(run.baseline_values(baseline)) == BASELINE_ID


def test_config_id_think_and_model():
    values = {"harness": "go", "tools": "bash", "env": "docker", "codebase": "rust",
              "model": "qwen3:14b", "think": True}
    assert run.config_id(values) == "go.bash.docker.rust.qwen3-14b.think"


def test_full_grid_has_162_configurations():
    grid, _ = load_grid_and_baseline()
    configs = run.all_configs(grid)
    assert len(configs) == 162
    assert len({run.config_id(c) for c in configs}) == 162


def test_stage_1_is_the_baseline():
    grid, baseline = load_grid_and_baseline()
    selected = run.select_configs(run.all_configs(grid), run.baseline_values(baseline), 1)
    assert [run.config_id(c) for c in selected] == [BASELINE_ID]


def test_stage_2_has_10_configurations_in_grid_order():
    grid, baseline = load_grid_and_baseline()
    configs = run.all_configs(grid)
    base = run.baseline_values(baseline)
    selected = run.select_configs(configs, base, 2)
    assert len(selected) == 10
    assert BASELINE_ID in [run.config_id(c) for c in selected]
    assert all(run.differing_axes(c, base) <= 1 for c in selected)
    positions = [configs.index(c) for c in selected]
    assert positions == sorted(positions)


def test_no_stage_is_all_configurations():
    grid, baseline = load_grid_and_baseline()
    configs = run.all_configs(grid)
    assert run.select_configs(configs, run.baseline_values(baseline), None) == configs


def test_config_flag_picks_ids_in_grid_order(capsys):
    grid, _ = load_grid_and_baseline()
    configs = run.all_configs(grid)
    docker_rust = "py.files-bash.docker.rust.qwen3-8b.no-think"
    picked = run.pick_configs(configs, [docker_rust, BASELINE_ID])
    assert [run.config_id(c) for c in picked] == [BASELINE_ID, docker_rust]
    assert run.unknown_ids(configs, [BASELINE_ID, "nope"]) == ["nope"]
    assert run.main(["--dry-run", "--config", f"{docker_rust},{BASELINE_ID}", "--config", BASELINE_ID]) == 0
    assert capsys.readouterr().out.splitlines() == [BASELINE_ID, docker_rust, "2 configurations"]
    assert run.main(["--dry-run", "--stage", "1", "--config", docker_rust]) == 2
    assert run.main(["--dry-run", "--config", "nope"]) == 2


def test_config_file_replaces_axis_values(tmp_path):
    _, baseline = load_grid_and_baseline()
    values = dict(run.baseline_values(baseline), think=True)
    path = run.write_config(tmp_path, run.config_id(values), run.build_config(baseline, values))
    written = yaml.safe_load(path.read_text())
    assert written["think"] is True
    assert written["max_turns"] == baseline["max_turns"]
    assert path.parent.name == "py.files-bash.local.python.qwen3-8b.think"


def test_unknown_harness_raises_before_any_trial():
    with pytest.raises(suite.HarnessNotFound, match="HARNESS_COMMANDS"):
        suite.harness_command("rb")


# Skip logic


def test_trial_done(tmp_path):
    assert not suite.trial_done(tmp_path)
    (tmp_path / "result.json").write_text(json.dumps({"passed": None}))
    assert not suite.trial_done(tmp_path)
    (tmp_path / "result.json").write_text("{not json")
    assert not suite.trial_done(tmp_path)
    (tmp_path / "result.json").write_text(json.dumps({"passed": False}))
    assert suite.trial_done(tmp_path)


def test_run_suite_skips_done_trials(tmp_path, monkeypatch):
    make_task(tmp_path / "tasks")
    runs_dir = tmp_path / "runs"
    for n in (1, 2):
        trial_dir = runs_dir / BASELINE_ID / "task-01-cart" / f"trial-{n}"
        trial_dir.mkdir(parents=True)
        (trial_dir / "result.json").write_text(json.dumps({"passed": True}))

    def fail(*args, **kwargs):
        raise AssertionError("a done trial ran again")

    monkeypatch.setattr(suite, "run_trial", fail)
    _, baseline = load_grid_and_baseline()
    config = run.build_config(baseline, run.baseline_values(baseline))
    results = suite.run_suite(
        BASELINE_ID, config, tmp_path / "config.yaml",
        runs_dir=runs_dir, tasks_root=tmp_path / "tasks", trials=2,
    )
    assert results == []


# Metrics


def test_pass_metrics_example():
    counts = [(3, 3), (3, 1), (3, 0)]
    assert round(report.pass_at_1(counts), 3) == 0.444
    assert round(report.pass_at_k(counts, 3), 3) == 0.667
    assert round(report.pass_pow_k(counts), 3) == 0.333


def test_pass_at_k_matches_pass_at_1_for_k_1():
    counts = [(3, 3), (3, 1), (3, 0)]
    assert report.pass_at_k(counts, 1) == pytest.approx(report.pass_at_1(counts))


def test_report_main_writes_json(tmp_path):
    runs_dir = tmp_path / "runs"
    outcomes = {"A": [True, True, True], "B": [True, False, False], "C": [False, False, False]}
    for task, passes in outcomes.items():
        for n, passed in enumerate(passes, start=1):
            trial_dir = runs_dir / BASELINE_ID / task / f"trial-{n}"
            trial_dir.mkdir(parents=True)
            result = {"passed": passed, "seconds": 10.0, "turns": 4, "prompt_tokens": 1000,
                      "completion_tokens": 100, "stop_reason": "end_turn", "flagged": task == "C"}
            (trial_dir / "result.json").write_text(json.dumps(result))
    assert report.main(["--runs", str(runs_dir)]) == 0
    row = json.loads((runs_dir / "report.json").read_text())["configs"][0]
    assert row["trials"] == 9 and row["k"] == 3
    assert round(row["pass_at_1"], 3) == 0.444
    assert round(row["pass_pow_k"], 3) == 0.333
    assert row["seconds_per_solved_task"] == pytest.approx(90.0 / 4)
    assert row["flagged"] == 3 and row["infra_error"] == 0


# Grading


def test_transcript_flag(tmp_path):
    path = tmp_path / "transcript.jsonl"
    clean = [
        {"type": "user", "content": "Do not read hidden_tests."},
        {"type": "assistant", "content": "", "tool_calls": [
            {"id": "a", "name": "bash", "arguments": {"command": "ls"}}]},
        {"type": "tool_result", "tool_call_id": "a", "name": "bash", "content": "cart.py"},
    ]
    path.write_text("".join(json.dumps(r) + "\n" for r in clean))
    assert not grade.transcript_flagged(path)
    leak = {"type": "tool_result", "tool_call_id": "b", "name": "bash", "content": "../solution/cart.py"}
    path.write_text(path.read_text() + json.dumps(leak) + "\n")
    assert grade.transcript_flagged(path)
    assert not grade.transcript_flagged(tmp_path / "missing.jsonl")


# End to end with the fake harness


def test_suite_passes_a_fixed_task(fake_run, tmp_path):
    [result] = fake_run("fix")
    assert result["passed"] is True
    assert result["flagged"] is False
    assert result["stop_reason"] == "end_turn"
    assert result["task"] == "task-01-cart" and result["trial"] == 1
    trial_dir = tmp_path / "runs" / BASELINE_ID / "task-01-cart" / "trial-1"
    assert (trial_dir / "prompt.txt").read_text() == "The cart total ignores the quantity. Fix it."
    assert "stop_reason=end_turn" in (trial_dir / "harness.log").read_text()
    assert json.loads((trial_dir / "result.json").read_text())["passed"] is True


def test_suite_flags_a_read_of_hidden_tests(fake_run):
    [result] = fake_run("cheat")
    assert result["flagged"] is True


def test_suite_records_a_crash_as_infra_error(fake_run):
    [result] = fake_run("crash")
    assert result["stop_reason"] == "infra_error"
    assert result["exit_code"] == 3
    assert result["passed"] is False
    assert set(result) >= {"config_id", "turns", "prompt_tokens", "model_digest", "grader_output", "flagged"}


def test_suite_kills_a_hung_harness(fake_run, tmp_path, monkeypatch):
    monkeypatch.setattr(suite, "TIMEOUT_GRACE_SECONDS", 0)
    start = time.monotonic()
    [result] = fake_run("hang", limits={"max_turns": 40, "max_seconds": 1})
    assert time.monotonic() - start < 15
    assert result["stop_reason"] == "infra_error"
    assert result["passed"] is False
    task_config = tmp_path / "runs" / BASELINE_ID / "task-01-cart" / "config.yaml"
    assert yaml.safe_load(task_config.read_text())["max_seconds"] == 1


def test_run_main_stage_1_then_resume(fake_run, tmp_path, monkeypatch, capsys):
    fake_run("fix")  # writes the fake task and sets up the fake harness
    runs_dir = tmp_path / "main-runs"
    monkeypatch.setattr(run, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(run, "TASKS_ROOT", tmp_path / "tasks")
    assert run.main(["--stage", "1", "--trials", "1", "--tasks", "cart"]) == 0
    assert (runs_dir / BASELINE_ID / "config.yaml").is_file()
    assert suite.trial_done(runs_dir / BASELINE_ID / "task-01-cart" / "trial-1")
    capsys.readouterr()
    assert run.main(["--stage", "1", "--trials", "1"]) == 0
    assert "skipped (done)" in capsys.readouterr().out
    assert run.main(["--stage", "1", "--tasks", "nope"]) == 2


# Task validation


def test_validate_tasks_accepts_a_good_task(tmp_path):
    make_task(tmp_path / "tasks")
    assert run.validate_tasks(tmp_path / "tasks", None) == 0


def test_validate_tasks_rejects_a_bad_solution(tmp_path):
    make_task(tmp_path / "tasks", solution=BUGGY)
    assert run.validate_tasks(tmp_path / "tasks", None) == 1
