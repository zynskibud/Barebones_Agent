"""Grade one trial.

Copy hidden_tests/ into the working folder and run the task test_command there.
The trial passes if the command exits with code 0.
Then fill passed, grader_output, and flagged in the result.json that the harness wrote.
If the harness wrote no result.json, write one with stop_reason infra_error and passed false.

flagged is true if a tool call argument or a tool result in transcript.jsonl
holds the string hidden_tests or solution. The spec (section 11) does not list this key yet.

This file also holds the small process and copy helpers that suite.py and run.py use.
"""

import json
import os
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path
from typing import IO, Any

REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_TIMEOUT_SECONDS = 300
GRADER_OUTPUT_CHARS = 4000
LEAK_STRINGS = ("hidden_tests", "solution")
COPY_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".DS_Store")


def project_env() -> dict[str, str]:
    """Return the environment with the project's .venv/bin first on PATH."""
    env = dict(os.environ)
    venv_bin = REPO_ROOT / ".venv" / "bin"
    env["PATH"] = f"{venv_bin}{os.pathsep}{env.get('PATH', '')}"
    return env


def kill_group(proc: subprocess.Popen) -> None:
    """Kill the process and every process in its group."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def run_command(
    command: list[str] | str,
    cwd: Path,
    stdout: IO[bytes],
    timeout: float,
    shell: bool = False,
) -> tuple[int, bool]:
    """Run a command in its own process group and return (exit code, timed out).

    stdout and stderr both go to the open file. On a timeout or an interrupt,
    the whole process group is killed, so no child process stays alive.
    """
    proc = subprocess.Popen(
        command,
        cwd=cwd,
        env=project_env(),
        stdin=subprocess.DEVNULL,
        stdout=stdout,
        stderr=subprocess.STDOUT,
        shell=shell,
        start_new_session=True,
    )
    try:
        return proc.wait(timeout=timeout), False
    except subprocess.TimeoutExpired:
        kill_group(proc)
        return proc.wait(), True
    except BaseException:
        kill_group(proc)
        proc.wait()
        raise


def copy_tree(src: Path, dst: Path) -> None:
    """Copy the contents of src into dst. dst can exist already."""
    shutil.copytree(src, dst, ignore=COPY_IGNORE, dirs_exist_ok=True)


def install_hidden_tests(task_dir: Path, workdir: Path) -> None:
    """Copy the task hidden_tests/ into the working folder.

    Anything that the agent left at workdir/hidden_tests is deleted first.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    target = workdir / "hidden_tests"
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.is_dir():
        shutil.rmtree(target)
    shutil.copytree(task_dir / "hidden_tests", target, ignore=COPY_IGNORE)


def run_tests(workdir: Path, test_command: str) -> tuple[bool, str]:
    """Run test_command in the working folder. Return (passed, output)."""
    with tempfile.TemporaryFile() as out:
        exit_code, timed_out = run_command(
            test_command, workdir, out, TEST_TIMEOUT_SECONDS, shell=True
        )
        out.seek(0)
        output = out.read().decode("utf-8", errors="replace")
    if timed_out:
        output += f"\n[grader] The tests ran longer than {TEST_TIMEOUT_SECONDS} seconds and were stopped.\n"
    return exit_code == 0 and not timed_out, output


def read_result(path: Path) -> dict[str, Any] | None:
    """Return the result.json contents, or None if the file is missing or not valid."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def write_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON through a temp file, so a stopped run never leaves half a file."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def infra_error_result(
    config_id: str,
    config: dict[str, Any],
    task: str,
    trial: int,
    exit_code: int,
    seconds: float,
) -> dict[str, Any]:
    """Return a result with the spec keys for a harness that wrote no result.json."""
    return {
        "config_id": config_id,
        "task": task,
        "trial": trial,
        "stop_reason": "infra_error",
        "turns": None,
        "seconds": round(seconds, 1),
        "prompt_tokens": None,
        "completion_tokens": None,
        "model": config.get("model"),
        "model_digest": None,
        "num_ctx": config.get("num_ctx"),
        "temperature": config.get("temperature"),
        "think": config.get("think"),
        "exit_code": exit_code,
        "tool_calls": None,
        "malformed_tool_calls": None,
        "passed": None,
        "grader_output": None,
    }


def has_leak(text: str) -> bool:
    """Return True if the text holds hidden_tests or solution."""
    return any(word in text for word in LEAK_STRINGS)


def tool_texts(record: dict[str, Any]) -> list[str]:
    """Return the tool call arguments and tool results in one transcript record."""
    if record.get("type") == "assistant":
        calls = record.get("tool_calls") or []
        return [json.dumps(call.get("arguments")) for call in calls if isinstance(call, dict)]
    if record.get("type") == "tool_result":
        return [str(record.get("content", ""))]
    return []


def transcript_flagged(path: Path) -> bool:
    """Return True if a tool call or tool result in the transcript names hidden_tests or solution.

    A line that is not valid JSON is searched as plain text.
    """
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return False
    for line in lines:
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError:
            if has_leak(line):
                return True
            continue
        if isinstance(record, dict) and any(has_leak(text) for text in tool_texts(record)):
            return True
    return False


def grade_trial(
    task_dir: Path,
    test_command: str,
    workdir: Path,
    trial_dir: Path,
    *,
    config_id: str,
    config: dict[str, Any],
    task: str,
    trial: int,
    exit_code: int,
    seconds: float,
) -> dict[str, Any]:
    """Run the hidden tests, update result.json in trial_dir, and return the result.

    The eval harness sets task and trial, because the harness flags do not carry them.
    """
    install_hidden_tests(task_dir, workdir)
    passed, output = run_tests(workdir, test_command)
    result_path = trial_dir / "result.json"
    result = read_result(result_path)
    if result is None:
        result = infra_error_result(config_id, config, task, trial, exit_code, seconds)
        passed = False
    result.setdefault("config_id", config_id)
    result["task"] = task
    result["trial"] = trial
    result["passed"] = passed
    result["grader_output"] = output[-GRADER_OUTPUT_CHARS:]
    result["flagged"] = transcript_flagged(trial_dir / "transcript.jsonl")
    write_json(result_path, result)
    return result
