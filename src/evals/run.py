"""Run the evals: grid to configurations to suites.

Usage:
    uv run python src/evals/run.py [--stage 1|2] [--config <id>[,<id>]]... [--dry-run]
                                   [--keep] [--trials N] [--tasks a,b] [--runs <folder>]
                                   [--set key=value]... [--validate-tasks] [--allow-local-bash]

config/grid.yaml gives the axes. config/baseline.yaml gives the baseline value on every
axis and the defaults for every other key (num_ctx, temperature, max_turns, max_seconds).
The configurations come from itertools.product over the axes, in grid order.
Grid order is the run order.

--stage 1 runs the baseline only. --stage 2 runs the baseline and every configuration
that differs from it on exactly one axis. No --stage runs all configurations.
--config selects exact configuration IDs from the grid. Repeat the flag or separate the
IDs with commas. With --stage, only the IDs in that stage run. An ID that is not in the
grid is an error.

For each configuration, run.py writes runs/<config id>/config.yaml and runs the suite.
The suite skips trials that already have a graded result.json, so a stopped run continues.
--runs puts the results in another folder, for example runs/smoke for a check that must
not touch the eval results. report.py --runs reads the same folder.

--set key=value adds one key to every config.yaml that the run writes, after the axis
values. Repeat the flag for more keys. The value gets the flat config typing: null, true,
false, a number, or else text. A key that names an axis is an error, because the axis
values come from the grid. The configuration ID does not show --set keys, so a run with
another value, for example --set prompt=config/system_prompt_v2.txt, needs its own --runs folder.

--tasks takes task folder names or task.yaml names, separated by commas.
--validate-tasks checks every task under tasks/<codebase>/: repo/ plus hidden_tests/ must
fail the test_command, and repo/ with solution/ copied over it plus hidden_tests/ must pass.

env: local has no sandbox for bash: the safe_path fence wraps only the file tools. A
configuration with env: local and a tool set that includes bash (bash or files-bash) is
blocked. --allow-local-bash removes the block, for a session that has the owner's word.
A blocked configuration is skipped and printed, not treated as an error, so the rest of
the selection still runs. --dry-run marks blocked configurations the same way.
"""

import argparse
import itertools
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

import grade
import suite

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
TASKS_ROOT = REPO_ROOT / "tasks"
RUNS_DIR = REPO_ROOT / "runs"
# The axes in configuration ID order.
ID_AXES = ("harness", "tools", "env", "codebase", "model", "think")


def load_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML file into a dict."""
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def model_id(tag: str) -> str:
    """Return the Ollama tag with ':' changed to '-'."""
    return tag.replace(":", "-")


def think_id(think: bool) -> str:
    """Return 'think' or 'no-think'."""
    return "think" if think else "no-think"


def config_id(values: dict[str, Any]) -> str:
    """Return <harness>.<tools>.<env>.<codebase>.<model-id>.<think-id>."""
    return ".".join([
        values["harness"],
        values["tools"],
        values["env"],
        values["codebase"],
        model_id(values["model"]),
        think_id(values["think"]),
    ])


def all_configs(grid: dict[str, list[Any]]) -> list[dict[str, Any]]:
    """Return every combination of the axes, in grid order."""
    if set(grid) != set(ID_AXES):
        raise ValueError(f"grid.yaml must have exactly these axes: {', '.join(ID_AXES)}")
    axes = list(grid)
    return [dict(zip(axes, values)) for values in itertools.product(*grid.values())]


def baseline_values(baseline: dict[str, Any]) -> dict[str, Any]:
    """Return the baseline value on each axis."""
    return {axis: baseline[axis] for axis in ID_AXES}


def differing_axes(values: dict[str, Any], baseline: dict[str, Any]) -> int:
    """Return the number of axes on which values differ from the baseline."""
    return sum(values[axis] != baseline[axis] for axis in ID_AXES)


def select_configs(
    configs: list[dict[str, Any]], baseline: dict[str, Any], stage: int | None
) -> list[dict[str, Any]]:
    """Return the configurations for the stage, in grid order.

    Stage 1: the baseline. Stage 2: the baseline and one-axis changes. None: all.
    """
    if not any(differing_axes(c, baseline) == 0 for c in configs):
        raise ValueError("The baseline is not in the grid.")
    if stage is None:
        return configs
    limit = 0 if stage == 1 else 1
    return [c for c in configs if differing_axes(c, baseline) <= limit]


BLOCKED_LOCAL_BASH_MESSAGE = (
    "blocked (local env with a bash tool set; pass --allow-local-bash to run on the host): "
)


def blocked_local_bash(values: dict[str, Any]) -> bool:
    """Return True if this configuration runs the bash tool directly on the host.

    env: local has no sandbox: safe_path fences only the file tools, so a bash or
    files-bash tool set on local can read or write anywhere the user can. This
    configuration needs the owner's explicit --allow-local-bash to run.
    """
    return values["env"] == "local" and values["tools"] in ("bash", "files-bash")


def print_blocked(values: dict[str, Any]) -> None:
    """Print the one-line message for a configuration that the guard skips."""
    print(f"{BLOCKED_LOCAL_BASH_MESSAGE}{config_id(values)}")


def pick_configs(configs: list[dict[str, Any]], ids: list[str]) -> list[dict[str, Any]]:
    """Return the configurations whose ID is in ids, in grid order."""
    wanted = set(ids)
    return [c for c in configs if config_id(c) in wanted]


def unknown_ids(configs: list[dict[str, Any]], ids: list[str]) -> list[str]:
    """Return the IDs that name no configuration in configs, sorted."""
    known = {config_id(c) for c in configs}
    return sorted(set(ids) - known)


def build_config(
    baseline: dict[str, Any], values: dict[str, Any], overrides: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Return the baseline with the axis values replaced, then the --set keys."""
    config = dict(baseline)
    config.update(values)
    config.update(overrides or {})
    return config


def parse_value(raw: str) -> Any:
    """Type one --set value as the flat config file does: null, true, false, a number, or text."""
    if raw in ("", "null", "~"):
        return None
    if raw in ("true", "True"):
        return True
    if raw in ("false", "False"):
        return False
    for number in (int, float):
        try:
            return number(raw)
        except ValueError:
            pass
    return raw


def parse_overrides(pairs: list[str]) -> dict[str, Any]:
    """Turn --set key=value pairs into a dict. Raise ValueError for a bad pair or an axis key."""
    overrides: dict[str, Any] = {}
    for pair in pairs:
        key, equals, raw = pair.partition("=")
        key = key.strip()
        if not equals or not key:
            raise ValueError(f"--set needs key=value, not '{pair}'")
        if key in ID_AXES:
            raise ValueError(f"--set cannot change the axis '{key}'. The axis values come from the grid.")
        overrides[key] = parse_value(raw.strip())
    return overrides


def write_config(runs_dir: Path, cid: str, config: dict[str, Any]) -> Path:
    """Write runs/<config id>/config.yaml and return its path."""
    folder = runs_dir / cid
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "config.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return path


def known_task_names(tasks_root: Path) -> set[str]:
    """Return every task folder name and task.yaml name under tasks/."""
    names: set[str] = set()
    for codebase_dir in sorted(tasks_root.iterdir()) if tasks_root.is_dir() else []:
        for task_dir in suite.list_task_dirs(codebase_dir):
            names.add(task_dir.name)
            try:
                names.add(str(suite.load_task(task_dir)["name"]))
            except (ValueError, yaml.YAMLError):
                pass
    return names


def tests_pass(task_dir: Path, test_command: str, with_solution: bool) -> tuple[bool, str]:
    """Run the hidden tests on repo/ (or on repo/ with solution/ over it) in a temp folder."""
    workdir = Path(tempfile.mkdtemp(prefix="barebones-validate-")).resolve()
    try:
        grade.copy_tree(task_dir / "repo", workdir)
        if with_solution:
            grade.copy_tree(task_dir / "solution", workdir)
        grade.install_hidden_tests(task_dir, workdir)
        return grade.run_tests(workdir, test_command)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def last_line(text: str) -> str:
    """Return the last line of text that is not empty."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def validate_task(task_dir: Path) -> dict[str, Any]:
    """Check one task. repo/ must fail the hidden tests. solution/ must pass them."""
    row = {"task": f"{task_dir.parent.name}/{task_dir.name}", "repo": "-", "solution": "-", "ok": False, "note": ""}
    try:
        task = suite.load_task(task_dir)
    except (ValueError, yaml.YAMLError) as error:
        row["note"] = str(error)
        return row
    for part in ("repo", "solution", "hidden_tests"):
        if not (task_dir / part).is_dir():
            row["note"] = f"no {part}/ folder"
            return row
    repo_passed, _ = tests_pass(task_dir, task["test_command"], with_solution=False)
    solution_passed, solution_output = tests_pass(task_dir, task["test_command"], with_solution=True)
    row["repo"] = "pass" if repo_passed else "fail"
    row["solution"] = "pass" if solution_passed else "fail"
    row["ok"] = not repo_passed and solution_passed
    if repo_passed:
        row["note"] = "repo/ passes the hidden tests"
    elif not solution_passed:
        row["note"] = "solution/ fails: " + last_line(solution_output)[:80]
    return row


def validate_tasks(tasks_root: Path, names: list[str] | None) -> int:
    """Check every task in every codebase. Print a table. Return 1 if a task fails."""
    rows = []
    for codebase_dir in sorted(tasks_root.iterdir()) if tasks_root.is_dir() else []:
        if not codebase_dir.is_dir() or codebase_dir.name.startswith("."):
            continue
        for task_dir in sorted(d for d in codebase_dir.iterdir() if d.is_dir() and not d.name.startswith(".")):
            if names and task_dir.name not in names:
                try:
                    if suite.load_task(task_dir)["name"] not in names:
                        continue
                except (ValueError, yaml.YAMLError):
                    continue
            rows.append(validate_task(task_dir))
    if not rows:
        print(f"No tasks found under {tasks_root}.")
        return 1
    width = max(len(r["task"]) for r in rows)
    print(f"{'task':<{width}}  {'repo+tests':<10}  {'solution+tests':<14}  check  note")
    for r in rows:
        check = "OK" if r["ok"] else "BAD"
        print(f"{r['task']:<{width}}  {r['repo']:<10}  {r['solution']:<14}  {check:<5}  {r['note']}")
    bad = sum(not r["ok"] for r in rows)
    print(f"{len(rows)} tasks, {bad} bad")
    return 1 if bad else 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(description="Run the evals over the configuration grid.")
    parser.add_argument("--stage", type=int, choices=[1, 2], help="1: baseline only. 2: one axis at a time.")
    parser.add_argument(
        "--config", action="append", metavar="ID",
        help="Run this configuration ID. Repeat the flag or separate IDs with commas.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the configuration IDs and exit.")
    parser.add_argument("--keep", action="store_true", help="Keep the temp working folders.")
    parser.add_argument("--trials", type=int, default=3, help="Trials per task (default 3).")
    parser.add_argument("--tasks", help="Task names, separated by commas.")
    parser.add_argument("--runs", type=Path, default=None, help="The results folder (default runs/).")
    parser.add_argument(
        "--set", action="append", default=[], metavar="KEY=VALUE", dest="set_pairs",
        help="Add this key to every config.yaml that the run writes. Repeat the flag for more keys. "
        "An axis key is an error. The configuration ID does not show the key, so give each value "
        "its own --runs folder, for example one folder per prompt version.",
    )
    parser.add_argument("--validate-tasks", action="store_true", help="Check every task and exit.")
    parser.add_argument(
        "--allow-local-bash", action="store_true",
        help="Run a configuration with env: local and a bash tool set. Blocked by default: "
        "local has no sandbox for bash. Use only with the owner's explicit word.",
    )
    args = parser.parse_args(argv)
    if args.trials < 1:
        parser.error("--trials must be 1 or more")
    try:
        args.overrides = parse_overrides(args.set_pairs)
    except ValueError as error:
        parser.error(str(error))
    args.task_names = [n.strip() for n in args.tasks.split(",") if n.strip()] if args.tasks else None
    args.config_ids = [c.strip() for raw in (args.config or []) for c in raw.split(",") if c.strip()]
    return args


def main(argv: list[str] | None = None) -> int:
    """Run the command line. Return the exit code."""
    args = parse_args(argv)
    if args.validate_tasks:
        return validate_tasks(TASKS_ROOT, args.task_names)

    grid = load_yaml(CONFIG_DIR / "grid.yaml")
    baseline = load_yaml(CONFIG_DIR / "baseline.yaml")
    configs = all_configs(grid)
    selected = select_configs(configs, baseline_values(baseline), args.stage)
    if args.config_ids:
        unknown = unknown_ids(configs, args.config_ids)
        if unknown:
            print(f"Unknown configuration IDs: {', '.join(unknown)}", file=sys.stderr)
            return 2
        # With --stage, the IDs must be in the stage. Without it, they come from the whole grid.
        selected = pick_configs(selected, args.config_ids)
        if not selected:
            print("No selected configuration is in the stage.", file=sys.stderr)
            return 2

    if args.dry_run:
        blocked = 0
        for values in selected:
            if blocked_local_bash(values) and not args.allow_local_bash:
                print_blocked(values)
                blocked += 1
            else:
                print(config_id(values))
        print(f"{len(selected)} configuration{'' if len(selected) == 1 else 's'}")
        if blocked:
            print(f"{blocked} blocked")
        for key, value in args.overrides.items():
            # The line exactly as it goes into each config.yaml.
            print(f"set {yaml.safe_dump({key: value}).strip()}")
        return 0

    if args.task_names:
        unknown = sorted(set(args.task_names) - known_task_names(TASKS_ROOT))
        if unknown:
            print(f"Unknown tasks: {', '.join(unknown)}", file=sys.stderr)
            return 2

    runs_dir = args.runs if args.runs is not None else RUNS_DIR
    blocked = 0
    runnable = []
    for values in selected:
        if blocked_local_bash(values) and not args.allow_local_bash:
            print_blocked(values)
            blocked += 1
        else:
            runnable.append(values)
    print(f"{len(runnable)} configurations, {args.trials} trials per task. Results go to {runs_dir}.")
    try:
        for values in runnable:
            cid = config_id(values)
            suite.harness_command(values["harness"])
            config = build_config(baseline, values, args.overrides)
            config_path = write_config(runs_dir, cid, config)
            suite.run_suite(
                cid,
                config,
                config_path,
                runs_dir=runs_dir,
                tasks_root=TASKS_ROOT,
                trials=args.trials,
                keep=args.keep,
                task_names=args.task_names,
            )
    except suite.HarnessNotFound as error:
        print(error, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nStopped. Run the same command again to continue.", file=sys.stderr)
        return 130
    if blocked:
        print(f"{blocked} blocked")
    print("Done. Run src/evals/report.py for the table.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
