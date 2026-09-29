"""Score one Harbor job folder.

Usage:
    uv run python src/evals/harbor/score.py <job-folder>

Example: uv run python src/evals/harbor/score.py runs/harbor-tb21/tb21-subset

Reads every trial folder under the job folder (runs/<job>/<job-name>/<task>__<id>/) and
prints a per-task table, then the score. A trial is one of three kinds:

- no agent run: agent/result.json is missing (the agent phase never wrote one, for
  example because setup never finished). Excluded from the score.
- emulation: excluded: agent/result.json has stop_reason "wall_clock" (the adapter's
  real-time cap fired, docs/harbor.md "Time caps") or exit_code 139 (a crash, for
  example a segfault under the qemu emulation that Terminal-Bench 2.1 runs under).
  Excluded from the score, but shown with the reason.
- graded: every other trial. The score is the fraction with reward 1.

This also works on a job folder with one trial, for example runs/harbor-smoke/smoke.
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

EMULATION_EXIT_CODE = 139
TIMESTAMP_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}")


def read_json(path: Path) -> dict[str, Any] | None:
    """Return the parsed JSON file, or None if it is missing or not valid JSON."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def trial_log_seconds(path: Path) -> float | None:
    """Return the seconds between the first and last timestamp in trial.log, if present.

    trial.log has no timestamps in the runs seen so far (docs/harbor.md, "Time caps"),
    so this is None most of the time; it is here for the day a verbose log has them.
    """
    if not path.exists():
        return None
    stamps = [match.group(0) for match in TIMESTAMP_PATTERN.finditer(path.read_text(encoding="utf-8", errors="replace"))]
    if len(stamps) < 2:
        return None
    fmt = "%Y-%m-%dT%H:%M:%S" if "T" in stamps[0] else "%Y-%m-%d %H:%M:%S"
    try:
        first, last = datetime.strptime(stamps[0], fmt), datetime.strptime(stamps[-1], fmt)
    except ValueError:
        return None
    return (last - first).total_seconds()


def reward_of(trial_result: dict[str, Any] | None) -> float | None:
    """Return the verifier reward from Harbor's own trial result.json, if any."""
    if not trial_result:
        return None
    rewards = (trial_result.get("verifier_result") or {}).get("rewards") or {}
    return rewards.get("reward")


def load_trial(trial_dir: Path) -> dict[str, Any]:
    """Return one row of facts for a trial folder. See the module docstring for the kinds."""
    task = trial_dir.name.split("__")[0]
    agent_result = read_json(trial_dir / "agent" / "result.json")
    trial_result = read_json(trial_dir / "result.json")
    row = {
        "task": task,
        "reward": reward_of(trial_result),
        "stop_reason": None,
        "turns": None,
        "awake_seconds": None,
        "wall_seconds": None,
        "exit_code": None,
        "trial_seconds": trial_log_seconds(trial_dir / "trial.log"),
    }
    if agent_result is None:
        row["kind"] = "no_agent_run"
        return row
    row["stop_reason"] = agent_result.get("stop_reason")
    row["turns"] = agent_result.get("turns")
    row["awake_seconds"] = agent_result.get("seconds")
    row["wall_seconds"] = agent_result.get("wall_seconds")
    row["exit_code"] = agent_result.get("exit_code")
    if row["stop_reason"] == "wall_clock" or row["exit_code"] == EMULATION_EXIT_CODE:
        row["kind"] = "emulation_excluded"
    else:
        row["kind"] = "graded"
    return row


def collect(job_dir: Path) -> list[dict[str, Any]]:
    """Return one row per trial folder under job_dir, in name order."""
    return [load_trial(entry) for entry in sorted(job_dir.iterdir()) if entry.is_dir()]


def cell(value: Any) -> str:
    """Format one table cell. None prints as "-"."""
    return "-" if value is None else str(value)


def print_table(rows: list[dict[str, Any]]) -> None:
    """Print one row per trial: task, reward, stop_reason, turns, awake_s, wall_s, exit, trial_s."""
    headers = ["task", "reward", "stop_reason", "turns", "awake_s", "wall_s", "exit", "trial_s"]
    fields = ["task", "reward", "stop_reason", "turns", "awake_seconds", "wall_seconds", "exit_code", "trial_seconds"]
    widths = [max(len(headers[i]), *(len(cell(row[fields[i]])) for row in rows)) if rows else len(headers[i])
              for i in range(len(headers))]
    print("  ".join(header.ljust(width) for header, width in zip(headers, widths)))
    for row in rows:
        print("  ".join(cell(row[field]).ljust(width) for field, width in zip(fields, widths)))


def exclusion_reason(row: dict[str, Any]) -> str:
    """Return why one emulation-excluded row was excluded: the cap, or the crash code."""
    if row["stop_reason"] == "wall_clock":
        return "wall_clock"
    return f"exit {row['exit_code']}"


def summarize(rows: list[dict[str, Any]]) -> None:
    """Print the score, the emulation exclusions, and the no-agent-run exclusions."""
    graded = [row for row in rows if row["kind"] == "graded"]
    passed = [row for row in graded if row["reward"] == 1]
    excluded = [row for row in rows if row["kind"] == "emulation_excluded"]
    no_agent = [row for row in rows if row["kind"] == "no_agent_run"]
    score = len(passed) / len(graded) if graded else 0.0
    print()
    print(f"score: {len(passed)} of {len(graded)} graded tasks with reward 1 = {score:.3f}")
    if excluded:
        names = ", ".join(f"{row['task']} ({exclusion_reason(row)})" for row in excluded)
        print(f"emulation: excluded - {names}")
        print("note: expiry = emulation timeout; excluded from the score with a note")
    if no_agent:
        print(f"no agent run: excluded - {', '.join(row['task'] for row in no_agent)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("job_dir", help="a Harbor job folder, for example runs/harbor-tb21/tb21-subset")
    args = parser.parse_args(argv)
    job_dir = Path(args.job_dir)
    if not job_dir.is_dir():
        print(f"not a folder: {job_dir}", file=sys.stderr)
        return 1
    rows = collect(job_dir)
    if not rows:
        print(f"no trial folders under {job_dir}", file=sys.stderr)
        return 1
    print_table(rows)
    summarize(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
