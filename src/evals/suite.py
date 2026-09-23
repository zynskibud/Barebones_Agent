"""Run one configuration: tasks x trials.

For each task in tasks/<codebase>/ (sorted), for each trial 1..N:

1. Copy the task repo/ into a fresh temp folder. This is the working folder.
2. Write the task prompt to prompt.txt in the trial folder, not in the working folder.
3. Start the harness program as a separate process, with cwd = repo root and the flags
   in docs/harness-spec.md section 2. stdout and stderr go to harness.log.
4. Kill the harness process group if it runs longer than max_seconds + 60 seconds.
5. Grade the trial (grade.py), then delete the temp folder unless keep is set.

Trial files: runs/<config id>/<task>/trial-<n>/ holds prompt.txt, harness.log,
transcript.jsonl, and result.json.

Task limits: the harness reads max_turns and max_seconds from the config file.
If task.yaml sets limits that differ from the configuration, the suite writes
runs/<config id>/<task>/config.yaml with the task limits and gives that file to the harness.
Otherwise the harness gets runs/<config id>/config.yaml.

A trial is done when its result.json holds a graded passed value (true or false).
The suite skips done trials. It deletes and runs again a trial folder that is not done.
"""

import shlex
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

import yaml

import grade

# The command that starts each harness. Add ts and go here when they exist.
HARNESS_COMMANDS: dict[str, list[str]] = {
    "py": ["uv", "run", "python", "src/harness/python/main.py"],
}

REPO_ROOT = Path(__file__).resolve().parents[2]
TASKS_ROOT = REPO_ROOT / "tasks"
RUNS_DIR = REPO_ROOT / "runs"
TASK_KEYS = ("name", "type", "prompt", "test_command", "limits")
LIMIT_KEYS = ("max_turns", "max_seconds")
TIMEOUT_GRACE_SECONDS = 60


class HarnessNotFound(Exception):
    """No command is known for a harness."""


def harness_command(harness: str) -> list[str]:
    """Return the command that starts the harness, or raise HarnessNotFound."""
    if harness not in HARNESS_COMMANDS:
        raise HarnessNotFound(
            f"No command for harness '{harness}'. "
            "Add it to HARNESS_COMMANDS in src/evals/suite.py."
        )
    return HARNESS_COMMANDS[harness]


def load_task(task_dir: Path) -> dict[str, Any]:
    """Read task.yaml. Raise ValueError if a key is missing."""
    path = task_dir / "task.yaml"
    if not path.is_file():
        raise ValueError(f"{task_dir.name}: no task.yaml")
    task = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    missing = [key for key in TASK_KEYS if key not in task]
    if missing:
        raise ValueError(f"{task_dir.name}: task.yaml has no {', '.join(missing)}")
    return task


def list_task_dirs(codebase_dir: Path) -> list[Path]:
    """Return the task folders (folders with a task.yaml) in sorted order."""
    if not codebase_dir.is_dir():
        return []
    return sorted(d for d in codebase_dir.iterdir() if (d / "task.yaml").is_file())


def task_matches(task_dir: Path, task: dict[str, Any], names: list[str] | None) -> bool:
    """Return True if names is empty, or holds the folder name or the task name."""
    return not names or task_dir.name in names or task.get("name") in names


def load_tasks(codebase_dir: Path, names: list[str] | None) -> list[tuple[Path, dict[str, Any]]]:
    """Load every selected task before any trial starts."""
    tasks = [(d, load_task(d)) for d in list_task_dirs(codebase_dir)]
    return [(d, t) for d, t in tasks if task_matches(d, t, names)]


def trial_done(trial_dir: Path) -> bool:
    """Return True if result.json exists and holds a graded passed value."""
    result = grade.read_result(trial_dir / "result.json")
    return result is not None and isinstance(result.get("passed"), bool)


def task_config(config: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    """Return the config with the task limits in place of the config limits."""
    limits = task.get("limits") or {}
    merged = dict(config)
    for key in LIMIT_KEYS:
        if key in limits:
            merged[key] = limits[key]
    return merged


def config_for_task(
    config: dict[str, Any], config_path: Path, task: dict[str, Any], task_run_dir: Path
) -> tuple[dict[str, Any], Path]:
    """Return the config and the config file for one task.

    If the task limits differ, write a per-task config file and return it.
    """
    merged = task_config(config, task)
    if merged == config:
        return config, config_path
    task_run_dir.mkdir(parents=True, exist_ok=True)
    path = task_run_dir / "config.yaml"
    path.write_text(yaml.safe_dump(merged, sort_keys=False), encoding="utf-8")
    return merged, path


def start_harness(args: list[str], log_path: Path, timeout: float) -> tuple[int, float]:
    """Run the harness process. Return (exit code, wall seconds)."""
    start = time.monotonic()
    with open(log_path, "ab") as log:
        log.write(f"$ {shlex.join(args)}\n".encode())
        log.flush()
        exit_code, timed_out = grade.run_command(args, REPO_ROOT, log, timeout)
        if timed_out:
            log.write(f"\n[eval] The harness ran longer than {timeout} seconds and was stopped.\n".encode())
    return exit_code, time.monotonic() - start


def run_trial(
    command: list[str],
    config_id: str,
    config: dict[str, Any],
    config_path: Path,
    task_dir: Path,
    task: dict[str, Any],
    trial: int,
    trial_dir: Path,
    keep: bool,
) -> dict[str, Any]:
    """Run and grade one trial. Return the graded result."""
    shutil.rmtree(trial_dir, ignore_errors=True)
    trial_dir.mkdir(parents=True)
    prompt_path = trial_dir / "prompt.txt"
    prompt_path.write_text(task["prompt"], encoding="utf-8")
    # Resolve the temp path. On macOS /var is a symlink to /private/var.
    workdir = Path(tempfile.mkdtemp(prefix="barebones-")).resolve()
    try:
        grade.copy_tree(task_dir / "repo", workdir)
        args = [
            *command,
            "--config", str(config_path),
            "--workdir", str(workdir),
            "--mode", "task",
            "--prompt-file", str(prompt_path),
            "--transcript", str(trial_dir / "transcript.jsonl"),
            "--result", str(trial_dir / "result.json"),
        ]
        timeout = config["max_seconds"] + TIMEOUT_GRACE_SECONDS
        exit_code, seconds = start_harness(args, trial_dir / "harness.log", timeout)
        return grade.grade_trial(
            task_dir,
            task["test_command"],
            workdir,
            trial_dir,
            config_id=config_id,
            config=config,
            task=task_dir.name,
            trial=trial,
            exit_code=exit_code,
            seconds=seconds,
        )
    finally:
        if keep:
            print(f"kept working folder: {workdir}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)


def trial_line(config_id: str, task: str, trial: int, result: dict[str, Any]) -> str:
    """Return the one-line summary of a trial."""
    status = "passed" if result.get("passed") else "failed"
    seconds = result.get("seconds")
    shown = f"{seconds:.1f}s" if isinstance(seconds, (int, float)) else "-"
    return f"{config_id}  {task}  trial {trial}  {status}  {result.get('stop_reason')}  {shown}"


def run_suite(
    config_id: str,
    config: dict[str, Any],
    config_path: Path,
    *,
    runs_dir: Path = RUNS_DIR,
    tasks_root: Path = TASKS_ROOT,
    trials: int = 3,
    keep: bool = False,
    task_names: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Run every selected task and trial for one configuration.

    Return the results of the trials that ran now. Skipped trials are not in the list.
    """
    command = harness_command(config["harness"])
    runs_dir = runs_dir.resolve()
    config_path = config_path.resolve()
    codebase_dir = tasks_root / config["codebase"]
    tasks = load_tasks(codebase_dir, task_names)
    if not tasks:
        print(f"{config_id}  no tasks selected in {codebase_dir}")
        return []
    results = []
    for task_dir, task in tasks:
        task_run_dir = runs_dir / config_id / task_dir.name
        run_config, run_config_path = config_for_task(config, config_path, task, task_run_dir)
        for trial in range(1, trials + 1):
            trial_dir = task_run_dir / f"trial-{trial}"
            if trial_done(trial_dir):
                print(f"{config_id}  {task_dir.name}  trial {trial}  skipped (done)")
                continue
            result = run_trial(
                command, config_id, run_config, run_config_path,
                task_dir, task, trial, trial_dir, keep,
            )
            results.append(result)
            print(trial_line(config_id, task_dir.name, trial, result), flush=True)
    return results
