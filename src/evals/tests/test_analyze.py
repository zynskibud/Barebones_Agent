"""Tests for analyze.py.

Run: uv run python -m pytest src/evals -q
"""

import json
import sys
from pathlib import Path

import pytest

# The eval modules import each other as top-level modules, as they do when run as scripts.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import analyze  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_ID = "py.files-bash.docker.python.qwen3-8b.no-think"


def write_trial(runs_dir, task, trial, *, records, passed, stop_reason="end_turn",
                 turns=4, seconds=10.0, flagged=False):
    """Write one transcript.jsonl and result.json under runs_dir/CONFIG_ID/<task>/<trial>/."""
    trial_dir = runs_dir / CONFIG_ID / task / f"trial-{trial}"
    trial_dir.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(r) for r in records]
    (trial_dir / "transcript.jsonl").write_text("\n".join(lines) + "\n")
    result = {
        "config_id": CONFIG_ID, "task": task, "trial": trial, "passed": passed,
        "stop_reason": stop_reason, "turns": turns, "seconds": seconds, "flagged": flagged,
    }
    (trial_dir / "result.json").write_text(json.dumps(result))
    return trial_dir


def assistant(name, arguments):
    """Return one assistant transcript record with a single tool call."""
    return {"type": "assistant", "content": "", "tool_calls": [{"id": "call_1", "name": name, "arguments": arguments}]}


def test_blind_edit_first_pattern(tmp_path):
    runs_dir = tmp_path / "runs"
    write_trial(runs_dir, "task-01", 1, records=[assistant("edit_file", {"path": "a.py", "old_str": "", "new_str": "x"})], passed=True)
    reports = json.loads(_run_json(runs_dir))
    assert reports[0]["patterns"]["blind_edit_first"] == 1
    assert reports[0]["first_tool_call"] == {"edit_file": 1}


def test_repeat_loop_pattern(tmp_path):
    runs_dir = tmp_path / "runs"
    call = assistant("read_file", {"path": "a.py"})
    write_trial(runs_dir, "task-01", 1, records=[call, call, call], passed=False)
    reports = json.loads(_run_json(runs_dir))
    assert reports[0]["patterns"]["repeat_loop"] == 1


def test_no_repeat_loop_with_only_two_identical_calls(tmp_path):
    runs_dir = tmp_path / "runs"
    call = assistant("read_file", {"path": "a.py"})
    write_trial(runs_dir, "task-01", 1, records=[call, call], passed=False)
    reports = json.loads(_run_json(runs_dir))
    assert reports[0]["patterns"]["repeat_loop"] == 0


def test_claimed_done_failed_pattern(tmp_path):
    runs_dir = tmp_path / "runs"
    write_trial(runs_dir, "task-01", 1, records=[], passed=False, stop_reason="end_turn")
    reports = json.loads(_run_json(runs_dir))
    assert reports[0]["patterns"]["claimed_done_failed"] == 1


def test_limit_hit_pattern(tmp_path):
    runs_dir = tmp_path / "runs"
    write_trial(runs_dir, "task-01", 1, records=[], passed=False, stop_reason="max_turns")
    write_trial(runs_dir, "task-01", 2, records=[], passed=False, stop_reason="max_seconds")
    write_trial(runs_dir, "task-01", 3, records=[], passed=True, stop_reason="end_turn")
    reports = json.loads(_run_json(runs_dir))
    assert reports[0]["patterns"]["limit_hit"] == 2


def test_bash_and_test_command_counts(tmp_path):
    runs_dir = tmp_path / "runs"
    write_trial(runs_dir, "task-01", 1, records=[assistant("bash", {"command": "python -m pytest -q"})], passed=True)
    write_trial(runs_dir, "task-01", 2, records=[assistant("bash", {"command": "ls"})], passed=False)
    write_trial(runs_dir, "task-01", 3, records=[assistant("read_file", {"path": "a.py"})], passed=False)
    reports = json.loads(_run_json(runs_dir))
    rep = reports[0]
    assert rep["bash_trials"] == 2
    assert rep["test_command_trials"] == 1
    assert rep["tool_calls"] == {"bash": 2, "read_file": 1}


def test_flat_single_config_folder_is_read(tmp_path):
    """A single-configuration runs folder (task/trial, no config-id level), like a lever run."""
    runs_dir = tmp_path / "runs"
    trial_dir = runs_dir / "task-01" / "trial-1"
    trial_dir.mkdir(parents=True)
    (trial_dir / "transcript.jsonl").write_text(json.dumps(assistant("read_file", {"path": "a.py"})) + "\n")
    result = {"config_id": CONFIG_ID, "passed": True, "stop_reason": "end_turn", "turns": 2, "seconds": 5.0, "flagged": False}
    (trial_dir / "result.json").write_text(json.dumps(result))
    reports = json.loads(_run_json(runs_dir))
    assert len(reports) == 1
    assert reports[0]["config_id"] == CONFIG_ID
    assert reports[0]["trials"] == 1


def test_no_graded_trials_exits_nonzero(tmp_path, capsys):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    assert analyze.main([str(runs_dir)]) == 1
    assert "No graded trials" in capsys.readouterr().out


def test_config_flag_limits_the_report(tmp_path):
    runs_dir = tmp_path / "runs"
    write_trial(runs_dir, "task-01", 1, records=[], passed=True)
    other_dir = runs_dir / "other.config" / "task-01" / "trial-1"
    other_dir.mkdir(parents=True)
    (other_dir / "transcript.jsonl").write_text("")
    (other_dir / "result.json").write_text(json.dumps(
        {"config_id": "other.config", "passed": True, "stop_reason": "end_turn", "turns": 1, "seconds": 1.0, "flagged": False}
    ))
    reports = json.loads(_run_json(runs_dir, config=CONFIG_ID))
    assert len(reports) == 1
    assert reports[0]["config_id"] == CONFIG_ID


def test_smoke_against_real_stage2_v2_reports_nine_configurations():
    runs_dir = REPO_ROOT / "runs" / "stage2-v2"
    if not runs_dir.is_dir():
        pytest.skip("runs/stage2-v2 is not present on this machine.")
    assert analyze.main([str(runs_dir)]) == 0
    reports = json.loads(_run_json(runs_dir))
    assert len(reports) == 9


def _run_json(runs_dir, config=None):
    """Run analyze.main with --json and return the captured stdout text."""
    import io
    import contextlib

    argv = [str(runs_dir), "--json"]
    if config:
        argv += ["--config", config]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = analyze.main(argv)
    assert code == 0
    return buf.getvalue()
