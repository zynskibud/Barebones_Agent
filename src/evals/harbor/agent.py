"""The Harbor agent adapter: Harbor loads this class as a custom agent.

Harbor starts the task container and calls run(instruction, environment,
context). The adapter builds the Python harness with build_agent, sets
env: harbor with Harbor's environment, and runs the same loop as task mode
with the instruction as the prompt. It writes transcript.jsonl and
result.json into the Harbor agent log folder (<trial folder>/agent/) and
returns. Harbor then runs the task's verifier and writes its own reward.

This is the one place where evals code imports the harness in-process:
Harbor needs a Python class, not a program. The harness code does not change.

Config: config/baseline.yaml, then env: harbor, codebase: terminal-bench-2-1,
then the HARBOR_SET overrides, in key=value,key=value form. Example:
HARBOR_SET=prompt=config/system_prompt_v2.txt,think=true

Start it from the repo root with PYTHONPATH=. and
--agent src.evals.harbor.agent:BarebonesAgent (docs/harbor.md).

Time cap: docs/harbor.md, "Time caps". HARBOR_WALL_SECONDS bounds the real (wall-clock)
time of the agent phase, so a sleeping laptop cannot turn one task into hours of
qemu-emulated Terminal-Bench work. loop.py's own max_seconds budget is awake time only
(time.monotonic, which does not advance across a system sleep); this cap uses time.time,
which does.
"""

import asyncio
import json
import os
import sys
import threading
import time
import traceback
from pathlib import Path

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

REPO_ROOT = Path(__file__).resolve().parents[3]
HARNESS_DIR = REPO_ROOT / "src" / "harness" / "python"
if str(HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(HARNESS_DIR))

from build import build_agent, load_config, parse_scalar  # noqa: E402
from loop import run_loop  # noqa: E402
from main import EXIT_CODES, crash_run, make_writer, open_transcript, used_settings, write_result  # noqa: E402

BASELINE = REPO_ROOT / "config" / "baseline.yaml"
OVERRIDES_VARIABLE = "HARBOR_SET"
FIXED = {"env": "harbor", "codebase": "terminal-bench-2-1"}
WALL_SECONDS_VARIABLE = "HARBOR_WALL_SECONDS"
DEFAULT_WALL_SECONDS = 600.0


def harbor_config(overrides: str | None) -> dict:
    """Return the baseline config with env: harbor and the key=value overrides."""
    config = load_config(str(BASELINE))
    config.update(FIXED)
    for pair in (overrides or "").split(","):
        if not pair.strip():
            continue
        if "=" not in pair:
            raise ValueError(f"{OVERRIDES_VARIABLE} needs key=value pairs, got {pair!r}")
        key, raw = pair.split("=", 1)
        config[key.strip()] = parse_scalar(raw.strip())
    return config


def task_name(session_id: str | None, logs_dir: Path) -> str:
    """Return the Harbor task name.

    Harbor names the trial <task>__<7 characters> and the agent session
    <trial>__agent. Harbor cuts the task name to 32 characters.
    """
    trial = session_id or logs_dir.parent.name
    return trial.split("__")[0]


def wall_seconds_limit() -> float:
    """Return the real-time cap on the agent phase, in seconds."""
    raw = os.environ.get(WALL_SECONDS_VARIABLE)
    return float(raw) if raw else DEFAULT_WALL_SECONDS


def add_wall_seconds(path: Path, wall_seconds: float) -> None:
    """Add wall_seconds to a result.json the adapter already wrote."""
    data = json.loads(path.read_text(encoding="utf-8"))
    data["wall_seconds"] = round(wall_seconds, 1)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def wall_clock_run(seconds: float) -> dict:
    """The run facts for a trial that hit HARBOR_WALL_SECONDS before the loop finished.

    Like main.crash_run, the counts the harness could not observe are 0.
    """
    return {
        "stop_reason": "wall_clock",
        "turns": 0,
        "seconds": round(seconds, 1),
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "tool_calls": 0,
        "malformed_tool_calls": 0,
        "error": None,
    }


def write_wall_clock_result(config: dict, out_dir: Path, task: str, wall_seconds: float) -> dict:
    """Write result.json, and append the transcript end record, for a trial that hit the cap.

    expired (set by the caller) stops the loop thread from writing either file after this
    point, so this is the only write. See docs/harbor.md, "Time caps".
    """
    run = wall_clock_run(wall_seconds)
    used = {"model_digest": None, "num_ctx": config.get("num_ctx"), "temperature": config.get("temperature")}
    out_dir.mkdir(parents=True, exist_ok=True)
    result_path = out_dir / "result.json"
    write_result(str(result_path), config, run, used, EXIT_CODES["wall_clock"], task=task)
    add_wall_seconds(result_path, wall_seconds)
    transcript_path = out_dir / "transcript.jsonl"
    if transcript_path.exists():
        end = {"type": "end", "stop_reason": "wall_clock", "turns": run["turns"], "seconds": run["seconds"]}
        with transcript_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(end, ensure_ascii=False) + "\n")
    return run


async def find_workdir(environment: BaseEnvironment) -> str:
    """Return the container work root: the task workdir, or else the shell's start folder."""
    config = getattr(environment, "task_env_config", None)
    workdir = getattr(config, "workdir", None)
    if workdir:
        return workdir
    result = await environment.exec("pwd")
    return (result.stdout or "/").strip() or "/"


class BarebonesAgent(BaseAgent):
    """The Barebones Agent Python harness, run by Harbor."""

    @staticmethod
    def name() -> str:
        return "barebones-agent"

    def version(self) -> str | None:
        return "1"

    async def setup(self, environment: BaseEnvironment) -> None:
        """Nothing to install: the harness and the model stay on the host."""

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        """Run the loop on the instruction and write the transcript and result.json.

        HARBOR_WALL_SECONDS bounds the real time of this phase (docs/harbor.md,
        "Time caps"). The loop runs in a thread so that Harbor's event loop stays free.
        If the thread is not done by the cap, this stops waiting for it, sets expired so
        the thread's own writes become no-ops and its loop stops before its next model
        call, writes result.json itself with stop_reason "wall_clock", and returns so
        Harbor proceeds to the verifier. The thread may keep running briefly in the
        background; expired keeps it from touching the files once this has.
        """
        config = harbor_config(os.environ.get(OVERRIDES_VARIABLE))
        workdir = await find_workdir(environment)
        loop = asyncio.get_running_loop()
        options = {"environment": environment, "loop": loop}
        task = task_name(self.session_id, Path(self.logs_dir))
        out_dir = Path(self.logs_dir)
        expired = threading.Event()
        started = time.time()
        worker = asyncio.to_thread(run_task, config, workdir, options, instruction, out_dir, task, expired, started)
        try:
            run = await asyncio.wait_for(worker, timeout=wall_seconds_limit())
        except asyncio.TimeoutError:
            expired.set()
            run = write_wall_clock_result(config, out_dir, task, time.time() - started)
        context.n_input_tokens = run["prompt_tokens"]
        context.n_output_tokens = run["completion_tokens"]
        context.metadata = {"stop_reason": run["stop_reason"], "turns": run["turns"], "seconds": run["seconds"]}


def run_task(
    config: dict,
    workdir: str,
    options: dict,
    prompt: str,
    out_dir: Path,
    task: str,
    expired: threading.Event,
    started: float,
) -> dict:
    """Task mode on a Harbor environment. Mirrors main.run_task. Return the run facts.

    expired is set from outside, by the adapter, once HARBOR_WALL_SECONDS has passed
    (docs/harbor.md, "Time caps"). Once it is set, record becomes a no-op, run_loop
    stops before its next model call, and this writes no result.json: the adapter
    already wrote the authoritative one.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    transcript = open_transcript(str(out_dir / "transcript.jsonl"), config)
    base_record = make_writer(transcript)

    def record(entry: dict) -> None:
        if not expired.is_set():
            base_record(entry)

    try:
        agent = build_agent(config, workdir, options)
        prompt = prompt.rstrip()
        record({"type": "system", "content": agent.system_prompt})
        record({"type": "user", "content": prompt})
        messages = [
            {"role": "system", "content": agent.system_prompt},
            {"role": "user", "content": prompt},
        ]
        try:
            agent.env.start()
            run = run_loop(
                agent.model, agent.tools, messages, agent.max_turns, agent.max_seconds, record, expired.is_set
            )
        finally:
            agent.env.stop()
        used = used_settings(agent, config)
    except Exception:
        detail = traceback.format_exc()
        print(detail, file=sys.stderr, end="")
        run = crash_run(detail)
        record({"type": "end", "stop_reason": "infra_error", "turns": 0, "seconds": 0.0, "error": detail})
        used = {"model_digest": None, "num_ctx": config.get("num_ctx"), "temperature": config.get("temperature")}
    transcript.close()
    if not expired.is_set():
        result_path = out_dir / "result.json"
        write_result(str(result_path), config, run, used, EXIT_CODES[run["stop_reason"]], task=task)
        add_wall_seconds(result_path, time.time() - started)
    return run
