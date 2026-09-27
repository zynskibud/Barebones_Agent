"""Analyze transcripts and results per configuration.

Usage:
    uv run python src/evals/analyze.py <runs-dir> [--config <id>] [--json]

Reads every transcript.jsonl and result.json under a runs folder and prints, for each
configuration: the trial count, the stop reasons, the first tool call of each trial, the
tool call totals, how many trials used bash, how many of those ran a test command, the
flagged count, mean turns and seconds, and the per-task pass counts on one line. Then a
short "patterns" block with four named counts: blind_edit_first, repeat_loop,
claimed_done_failed, and limit_hit.

A runs folder can hold several configurations (runs/<config id>/<task>/<trial>/, like
runs/stage2-v2) or one configuration flat (runs/<task>/<trial>/, like a lever run). Either
shape is read here; the flat shape gets its configuration ID from result.json.
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import report  # noqa: E402  (the mean() helper)

REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_COMMANDS = ("pytest", "node --test", "cargo test")
LIMIT_STOP_REASONS = ("max_turns", "max_seconds")

Trial = tuple[str, str, Path, dict[str, Any]]  # (config_id, task, trial_dir, result)


def read_result(path: Path) -> dict[str, Any] | None:
    """Return the result.json contents if it is graded (passed is true or false)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("passed"), bool):
        return None
    return data


def find_trials(runs_dir: Path) -> list[Trial]:
    """Return one entry per graded trial under runs_dir, in either runs folder shape.

    Tries the nested layout first: runs_dir/<config id>/<task>/<trial>/result.json.
    Falls back to the flat, single-configuration layout: runs_dir/<task>/<trial>/result.json,
    reading the configuration ID from inside result.json.
    """
    trials = []
    for path in sorted(runs_dir.glob("*/*/*/result.json")):
        result = read_result(path)
        if result is None:
            continue
        config_id, task = path.relative_to(runs_dir).parts[:2]
        trials.append((config_id, task, path.parent, result))
    if trials:
        return trials
    for path in sorted(runs_dir.glob("*/*/result.json")):
        result = read_result(path)
        config_id = result.get("config_id") if result else None
        if not config_id:
            continue
        task = path.relative_to(runs_dir).parts[0]
        trials.append((config_id, task, path.parent, result))
    return trials


def load_transcript(path: Path) -> list[dict[str, Any]]:
    """Return the transcript records. A line that is not a JSON object is skipped."""
    if not path.is_file():
        return []
    records = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def tool_calls(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return every tool call in the transcript, in order: {"name", "arguments"}."""
    calls = []
    for record in records:
        if record.get("type") != "assistant":
            continue
        for call in record.get("tool_calls") or []:
            if isinstance(call, dict):
                calls.append({"name": call.get("name"), "arguments": call.get("arguments")})
    return calls


def is_test_command(arguments: Any) -> bool:
    """Return True if a bash call's command runs pytest, node --test, or cargo test."""
    command = arguments.get("command") if isinstance(arguments, dict) else None
    return isinstance(command, str) and any(cmd in command for cmd in TEST_COMMANDS)


def has_repeat_loop(calls: list[dict[str, Any]]) -> bool:
    """Return True if the same tool call (name and arguments) repeats 3+ times in a row."""
    return any(calls[i] == calls[i + 1] == calls[i + 2] for i in range(len(calls) - 2))


def short_task_id(task: str) -> str:
    """Return the task number from a folder name like task-01-cart-total, or the name itself."""
    parts = task.split("-")
    return parts[1] if len(parts) >= 2 and parts[0] == "task" else task


def summarize_config(config_id: str, trials: list[tuple[str, Path, dict[str, Any]]]) -> dict[str, Any]:
    """Return the analysis for one configuration's trials."""
    stop_reasons: Counter[str] = Counter()
    first_calls: Counter[str] = Counter()
    tool_totals: Counter[str] = Counter()
    task_outcomes: dict[str, list[bool]] = defaultdict(list)
    bash_trials = 0
    test_trials = 0
    flagged = 0
    blind_edit_first = 0
    repeat_loop = 0
    claimed_done_failed = 0
    limit_hit = 0
    turns_values: list[float] = []
    seconds_values: list[float] = []

    for task, trial_dir, result in trials:
        stop_reason = result.get("stop_reason")
        stop_reasons[stop_reason if isinstance(stop_reason, str) else "none"] += 1
        if isinstance(result.get("turns"), (int, float)):
            turns_values.append(result["turns"])
        if isinstance(result.get("seconds"), (int, float)):
            seconds_values.append(result["seconds"])
        if result.get("flagged") is True:
            flagged += 1
        task_outcomes[task].append(result.get("passed") is True)

        calls = tool_calls(load_transcript(trial_dir / "transcript.jsonl"))
        first_calls[calls[0]["name"] if calls else "none"] += 1
        for call in calls:
            tool_totals[call["name"] or "unknown"] += 1
        if any(c["name"] == "bash" for c in calls):
            bash_trials += 1
        if any(c["name"] == "bash" and is_test_command(c["arguments"]) for c in calls):
            test_trials += 1
        if calls and calls[0]["name"] == "edit_file":
            blind_edit_first += 1
        if has_repeat_loop(calls):
            repeat_loop += 1
        if stop_reason == "end_turn" and result.get("passed") is False:
            claimed_done_failed += 1
        if stop_reason in LIMIT_STOP_REASONS:
            limit_hit += 1

    return {
        "config_id": config_id,
        "trials": len(trials),
        "stop_reasons": dict(stop_reasons),
        "first_tool_call": dict(first_calls),
        "tool_calls": dict(tool_totals),
        "bash_trials": bash_trials,
        "test_command_trials": test_trials,
        "flagged": flagged,
        "mean_turns": report.mean(turns_values),
        "mean_seconds": report.mean(seconds_values),
        "per_task_passed": {task: (sum(v), len(v)) for task, v in sorted(task_outcomes.items())},
        "patterns": {
            "blind_edit_first": blind_edit_first,
            "repeat_loop": repeat_loop,
            "claimed_done_failed": claimed_done_failed,
            "limit_hit": limit_hit,
        },
    }


def format_counts(counts: dict[str, int]) -> str:
    """Return counts as 'name n, name n' in descending order, ties broken by name."""
    return ", ".join(f"{name} {n}" for n, name in sorted(((n, name) for name, n in counts.items()), reverse=True))


def format_config_report(rep: dict[str, Any]) -> str:
    """Return one configuration's analysis as text."""
    per_task = " ".join(f"{short_task_id(t)}:{c}/{n}" for t, (c, n) in rep["per_task_passed"].items())
    patterns = "  ".join(f"{name} {n}" for name, n in rep["patterns"].items())
    lines = [
        f"== {rep['config_id']} ==",
        f"trials: {rep['trials']}",
        f"stop reasons: {format_counts(rep['stop_reasons'])}",
        f"first tool call: {format_counts(rep['first_tool_call'])}",
        f"tool calls: {format_counts(rep['tool_calls'])}",
        f"bash: {rep['bash_trials']} of {rep['trials']} trials used it; "
        f"{rep['test_command_trials']} of {rep['trials']} trials ran a test command in it",
        f"flagged: {rep['flagged']}",
        f"mean turns: {report.fmt(rep['mean_turns'], 1)}  mean seconds: {report.fmt(rep['mean_seconds'], 1)}",
        f"per task: {per_task}",
        f"patterns: {patterns}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Print (or write as JSON) the analysis for every configuration. Return the exit code."""
    parser = argparse.ArgumentParser(description="Analyze transcripts and results per configuration.")
    parser.add_argument("runs_dir", type=Path, help="The runs folder to analyze.")
    parser.add_argument("--config", help="Limit the report to one configuration ID.")
    parser.add_argument("--json", action="store_true", help="Write the same data as JSON to stdout.")
    args = parser.parse_args(argv)

    trials = find_trials(args.runs_dir)
    if args.config:
        trials = [t for t in trials if t[0] == args.config]
    if not trials:
        extra = f" (configuration {args.config} not found.)" if args.config else ""
        print(f"No graded trials in {args.runs_dir}.{extra}")
        return 1

    by_config: dict[str, list[tuple[str, Path, dict[str, Any]]]] = defaultdict(list)
    for config_id, task, trial_dir, result in trials:
        by_config[config_id].append((task, trial_dir, result))
    reports = [summarize_config(config_id, by_config[config_id]) for config_id in sorted(by_config)]

    if args.json:
        print(json.dumps(reports, indent=2))
    else:
        for rep in reports:
            print(format_config_report(rep))
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
