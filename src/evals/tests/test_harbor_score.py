"""Tests for the Harbor scoring helper, on a synthetic job folder.

Run: uv run python -m pytest src/evals -q
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from src.evals.harbor import score  # noqa: E402


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def make_trial(
    job_dir: Path,
    name: str,
    agent_data: dict | None,
    *,
    reward: float | None,
) -> None:
    """Build one trial folder: <job_dir>/<name>/{agent/result.json, result.json}."""
    trial_dir = job_dir / name
    if agent_data is not None:
        write_json(trial_dir / "agent" / "result.json", agent_data)
    if reward is not None:
        write_json(trial_dir / "result.json", {"verifier_result": {"rewards": {"reward": reward}}})
    else:
        trial_dir.mkdir(parents=True, exist_ok=True)


def agent_result(stop_reason: str, exit_code: int, **extra) -> dict:
    base = {
        "stop_reason": stop_reason,
        "turns": 3,
        "seconds": 40.0,
        "wall_seconds": 45.0,
        "exit_code": exit_code,
    }
    base.update(extra)
    return base


def build_synthetic_job(job_dir: Path) -> None:
    """One trial of each kind the score helper must tell apart."""
    make_trial(job_dir, "task-pass__aaa1111", agent_result("end_turn", 0), reward=1)
    make_trial(job_dir, "task-zero__bbb2222", agent_result("end_turn", 0), reward=0)
    make_trial(job_dir, "task-wallclock__ccc3333", agent_result("wall_clock", 2, turns=0, seconds=600.0), reward=0)
    make_trial(job_dir, "task-crash__ddd4444", agent_result("max_seconds", 139), reward=0)
    make_trial(job_dir, "task-noagent__eee5555", None, reward=None)


def test_score_synthetic_job_folder(tmp_path, capsys):
    job_dir = tmp_path / "job"
    build_synthetic_job(job_dir)

    exit_code = score.main([str(job_dir)])
    assert exit_code == 0
    out = capsys.readouterr().out

    assert "task-pass" in out
    assert "score: 1 of 2 graded tasks with reward 1 = 0.500" in out
    assert "emulation: excluded - task-crash (exit 139), task-wallclock (wall_clock)" in out
    assert "note: expiry = emulation timeout; excluded from the score with a note" in out
    assert "no agent run: excluded - task-noagent" in out


def test_load_trial_kinds(tmp_path):
    job_dir = tmp_path / "job"
    build_synthetic_job(job_dir)
    rows = {row["task"]: row for row in score.collect(job_dir)}

    assert rows["task-pass"]["kind"] == "graded"
    assert rows["task-pass"]["reward"] == 1
    assert rows["task-zero"]["kind"] == "graded"
    assert rows["task-zero"]["reward"] == 0
    assert rows["task-wallclock"]["kind"] == "emulation_excluded"
    assert rows["task-wallclock"]["stop_reason"] == "wall_clock"
    assert rows["task-crash"]["kind"] == "emulation_excluded"
    assert rows["task-crash"]["exit_code"] == 139
    assert rows["task-noagent"]["kind"] == "no_agent_run"


def test_score_one_trial_smoke_folder(tmp_path, capsys):
    """The smoke job shape: one trial folder under the job folder."""
    job_dir = tmp_path / "smoke"
    make_trial(job_dir, "write-compressor__NaFk4Ea", agent_result("end_turn", 0), reward=0)

    exit_code = score.main([str(job_dir)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "score: 0 of 1 graded tasks with reward 1 = 0.000" in out
