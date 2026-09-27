"""Tests for report.py --compare.

Run: uv run python -m pytest src/evals -q
"""

import json
import re
import sys
from pathlib import Path

import pytest

# The eval modules import each other as top-level modules, as they do when run as scripts.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import report  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_ID = "py.files-bash.docker.python.qwen3-8b.no-think"


def write_trial(runs_dir, config_id, task, trial, passed, seconds=10.0, turns=4, nested=True):
    """Write one result.json. nested=True gives runs_dir/<config>/<task>/<trial>/.

    nested=False gives runs_dir/<task>/<trial>/ (a single-configuration runs folder),
    with config_id only inside result.json, as a lever run leaves it.
    """
    trial_dir = runs_dir / config_id / task / f"trial-{trial}" if nested else runs_dir / task / f"trial-{trial}"
    trial_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "config_id": config_id,
        "task": task,
        "trial": trial,
        "passed": passed,
        "seconds": seconds,
        "turns": turns,
        "stop_reason": "end_turn",
    }
    (trial_dir / "result.json").write_text(json.dumps(result))


def test_compare_prints_per_task_deltas_and_summary(tmp_path, capsys):
    baseline_dir = tmp_path / "baseline"
    experiment_dir = tmp_path / "experiment"
    for n, passed in enumerate([False, False], start=1):
        write_trial(baseline_dir, CONFIG_ID, "task-A", n, passed)
        write_trial(baseline_dir, CONFIG_ID, "task-B", n, passed)
    for n, passed in enumerate([True, True], start=1):
        write_trial(experiment_dir, CONFIG_ID, "task-A", n, passed)
    for n, passed in enumerate([True, False], start=1):
        write_trial(experiment_dir, CONFIG_ID, "task-B", n, passed)

    assert report.main(["--compare", str(baseline_dir), str(experiment_dir)]) == 0
    out = capsys.readouterr().out
    assert "task-A" in out and "0/2" in out and "2/2" in out and "+1.000" in out
    assert "task-B" in out and "1/2" in out and "+0.500" in out
    assert "pass@1: 0.000 -> 0.750 (delta +0.750)" in out
    assert "pass^k: 0.000 -> 0.500" in out


def test_compare_flat_experiment_folder_joins_by_config_id(tmp_path):
    """A single-configuration runs folder (task/trial, no config-id level) still joins by config_id."""
    baseline_dir = tmp_path / "baseline"
    experiment_dir = tmp_path / "experiment"
    write_trial(baseline_dir, CONFIG_ID, "task-A", 1, False, nested=True)
    write_trial(experiment_dir, CONFIG_ID, "task-A", 1, True, nested=False)
    assert report.main(["--compare", str(baseline_dir), str(experiment_dir)]) == 0


def test_compare_config_flag_limits_to_one_configuration(tmp_path, capsys):
    baseline_dir = tmp_path / "baseline"
    experiment_dir = tmp_path / "experiment"
    write_trial(baseline_dir, CONFIG_ID, "task-A", 1, True)
    write_trial(baseline_dir, "other.config", "task-A", 1, True)
    write_trial(experiment_dir, CONFIG_ID, "task-A", 1, True)
    assert report.main(["--compare", str(baseline_dir), str(experiment_dir), "--config", CONFIG_ID]) == 0
    out = capsys.readouterr().out
    assert "other.config" not in out


def test_compare_no_overlap_exits_nonzero_with_a_clear_message(tmp_path, capsys):
    baseline_dir = tmp_path / "baseline"
    experiment_dir = tmp_path / "experiment"
    write_trial(baseline_dir, "config.a", "task-A", 1, True)
    write_trial(experiment_dir, "config.b", "task-A", 1, True)
    assert report.main(["--compare", str(baseline_dir), str(experiment_dir)]) == 1
    assert "No configuration is present in both" in capsys.readouterr().out


def test_compare_stage2_against_itself_gives_zero_deltas(capsys):
    runs_dir = REPO_ROOT / "runs" / "stage2-v2"
    if not runs_dir.is_dir():
        pytest.skip("runs/stage2-v2 is not present on this machine.")
    assert report.main(["--compare", str(runs_dir), str(runs_dir)]) == 0
    out = capsys.readouterr().out
    deltas = re.findall(r"delta ([+-]\d+\.\d{3})\)", out)
    assert deltas and set(deltas) == {"+0.000"}
