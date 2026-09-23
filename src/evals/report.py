"""Report the results.

Usage:
    uv run python src/evals/report.py [--runs runs/]

Read every result.json under runs/, group the trials by configuration, print a table,
and write runs/report.json with the same numbers.
The configuration ID and the task come from the folder path: runs/<config id>/<task>/trial-<n>/.
Trials that are not graded yet (passed is null) are left out.

Metrics for one configuration, with n trials and c passed trials for each task:
- pass@1: passed trials / trials.
- pass@k: the mean over tasks of 1 - C(n-c, k) / C(n, k).
- pass^k: the fraction of tasks where all trials passed.
- k is the number of trials per task (the smallest count, if the counts differ).
"""

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

# (n trials, c passed trials) for one task.
Counts = list[tuple[int, int]]


def pass_at_1(counts: Counts) -> float:
    """Return passed trials / trials."""
    trials = sum(n for n, _ in counts)
    return sum(c for _, c in counts) / trials if trials else 0.0


def pass_at_k_task(n: int, c: int, k: int) -> float:
    """Return the unbiased pass@k estimate for one task: 1 - C(n-c, k) / C(n, k)."""
    if k < 1 or n < k:
        raise ValueError(f"pass@k needs 1 <= k <= n, got n={n} k={k}")
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def pass_at_k(counts: Counts, k: int) -> float:
    """Return the mean pass@k over tasks."""
    return sum(pass_at_k_task(n, c, k) for n, c in counts) / len(counts) if counts else 0.0


def pass_pow_k(counts: Counts) -> float:
    """Return the fraction of tasks where all trials passed."""
    return sum(1 for n, c in counts if n > 0 and c == n) / len(counts) if counts else 0.0


def load_results(runs_dir: Path) -> tuple[list[dict[str, Any]], int]:
    """Return (graded results, count of ungraded results).

    Each result gets _config and _task keys from its folder path.
    """
    results = []
    ungraded = 0
    for path in sorted(runs_dir.glob("*/*/*/result.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            ungraded += 1
            continue
        if not isinstance(data, dict) or not isinstance(data.get("passed"), bool):
            ungraded += 1
            continue
        rel = path.relative_to(runs_dir).parts
        data["_config"], data["_task"] = rel[0], rel[1]
        results.append(data)
    return results, ungraded


def numbers(results: list[dict[str, Any]], key: str) -> list[float]:
    """Return the numeric values of key. Missing and null values are left out."""
    values = [r.get(key) for r in results]
    return [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]


def mean(values: list[float]) -> float | None:
    """Return the mean, or None for an empty list."""
    return sum(values) / len(values) if values else None


def summarize(config: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the metrics for one configuration."""
    by_task: dict[str, list[bool]] = defaultdict(list)
    for r in results:
        by_task[r["_task"]].append(r["passed"])
    counts = [(len(v), sum(v)) for _, v in sorted(by_task.items())]
    k = min(n for n, _ in counts)
    passed = sum(c for _, c in counts)
    total_seconds = sum(numbers(results, "seconds"))
    return {
        "config_id": config,
        "tasks": len(counts),
        "trials": len(results),
        "passed": passed,
        "k": k,
        "pass_at_1": pass_at_1(counts),
        "pass_at_k": pass_at_k(counts, k),
        "pass_pow_k": pass_pow_k(counts),
        "seconds_per_solved_task": total_seconds / passed if passed else None,
        "mean_prompt_tokens": mean(numbers(results, "prompt_tokens")),
        "mean_completion_tokens": mean(numbers(results, "completion_tokens")),
        "mean_turns": mean(numbers(results, "turns")),
        "mean_seconds": mean(numbers(results, "seconds")),
        "flagged": sum(1 for r in results if r.get("flagged") is True),
        "infra_error": sum(1 for r in results if r.get("stop_reason") == "infra_error"),
    }


def build_report(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return one summary row per configuration, sorted by configuration ID."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in results:
        groups[r["_config"]].append(r)
    return [summarize(config, groups[config]) for config in sorted(groups)]


def fmt(value: float | None, digits: int) -> str:
    """Format a number, or '-' for None."""
    return "-" if value is None else f"{value:.{digits}f}"


# (header, row key, digits). digits None means an integer count.
COLUMNS = [
    ("trials", "trials", None),
    ("k", "k", None),
    ("pass@1", "pass_at_1", 3),
    ("pass@k", "pass_at_k", 3),
    ("pass^k", "pass_pow_k", 3),
    ("s/solved", "seconds_per_solved_task", 1),
    ("prompt_tok", "mean_prompt_tokens", 0),
    ("compl_tok", "mean_completion_tokens", 0),
    ("turns", "mean_turns", 1),
    ("seconds", "mean_seconds", 1),
    ("flagged", "flagged", None),
    ("infra", "infra_error", None),
]


def format_table(rows: list[dict[str, Any]]) -> str:
    """Return the report as a text table."""
    cells = [["config"] + [header for header, _, _ in COLUMNS]]
    for row in rows:
        cells.append([row["config_id"]] + [
            str(row[key]) if digits is None else fmt(row[key], digits)
            for _, key, digits in COLUMNS
        ])
    widths = [max(len(line[i]) for line in cells) for i in range(len(cells[0]))]
    lines = []
    for line in cells:
        first = line[0].ljust(widths[0])
        rest = [cell.rjust(width) for cell, width in zip(line[1:], widths[1:])]
        lines.append("  ".join([first, *rest]))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Print the table and write report.json. Return the exit code."""
    parser = argparse.ArgumentParser(description="Report pass rates and costs per configuration.")
    parser.add_argument("--runs", type=Path, default=REPO_ROOT / "runs", help="The runs folder (default runs/).")
    args = parser.parse_args(argv)
    runs_dir: Path = args.runs
    results, ungraded = load_results(runs_dir)
    if not results:
        print(f"No graded results in {runs_dir}.")
        return 1
    rows = build_report(results)
    print(format_table(rows))
    if ungraded:
        print(f"{ungraded} trials are not graded and are left out.")
    report_path = runs_dir / "report.json"
    report_path.write_text(json.dumps({"configs": rows}, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
