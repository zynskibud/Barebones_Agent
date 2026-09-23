"""Start the agent.

Chat mode: an interactive session in the terminal.
Task mode: one task, then exit. The eval harness starts it as a separate program.
"""

import argparse
import json
import sys
import traceback
from pathlib import Path

from build import Agent, build_agent, config_id, load_config
from loop import run_loop

EXIT_CODES = {
    "end_turn": 0,
    "max_turns": 2,
    "max_seconds": 2,
    "malformed_tool_call": 2,
    "infra_error": 3,
}

RESULT_PREVIEW_CHARS = 300


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.mode == "task":
        return run_task(args)
    return run_chat(args)


class Parser(argparse.ArgumentParser):
    """An argument parser that exits with the infra_error code on a usage error."""

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(EXIT_CODES["infra_error"], f"{self.prog}: error: {message}\n")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = Parser(description="Barebones Agent: one loop, a few tools, one local model.")
    parser.add_argument("--config", required=True, help="the config file")
    parser.add_argument("--workdir", required=True, help="the working folder; the agent works only here")
    parser.add_argument("--mode", choices=["chat", "task"], default="chat")
    parser.add_argument("--prompt-file", help="task mode: the file that holds the task prompt")
    parser.add_argument("--transcript", help="task mode: where to write transcript.jsonl")
    parser.add_argument("--result", help="task mode: where to write result.json")
    args = parser.parse_args(argv)
    if args.mode == "task":
        for flag in ("prompt_file", "transcript", "result"):
            if getattr(args, flag) is None:
                parser.error(f"--{flag.replace('_', '-')} is required in task mode")
    return args


def run_task(args: argparse.Namespace) -> int:
    """Run one task, write the transcript and the result, print the status line."""
    try:
        config = load_config(args.config)
        transcript = open_transcript(args.transcript, config)
    except OSError as error:
        print(f"cannot start: {error}", file=sys.stderr)
        print("stop_reason=infra_error turns=0 seconds=0.0")
        return EXIT_CODES["infra_error"]
    record = make_writer(transcript)
    try:
        agent = build_agent(config, args.workdir)
        prompt = Path(args.prompt_file).read_text(encoding="utf-8").rstrip()
        record({"type": "system", "content": agent.system_prompt})
        record({"type": "user", "content": prompt})
        messages = [
            {"role": "system", "content": agent.system_prompt},
            {"role": "user", "content": prompt},
        ]
        agent.env.start()
        try:
            run = run_loop(agent.model, agent.tools, messages, agent.max_turns, agent.max_seconds, record)
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
    exit_code = EXIT_CODES[run["stop_reason"]]
    write_result(args.result, config, run, used, exit_code)
    if run["error"]:
        print(run["error"].rstrip().splitlines()[-1], file=sys.stderr)
    print(f"stop_reason={run['stop_reason']} turns={run['turns']} seconds={run['seconds']}")
    return exit_code


def open_transcript(path: str, config: dict):
    """Open transcript.jsonl and write the config line."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "w", encoding="utf-8")
    line = {"type": "config", "config_id": config_id(config), "config": config}
    handle.write(json.dumps(line, ensure_ascii=False) + "\n")
    handle.flush()
    return handle


def make_writer(handle):
    """Return a record function that appends one JSON line per record."""

    def write(entry: dict) -> None:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        handle.flush()

    return write


def crash_run(detail: str) -> dict:
    """The run facts for a harness crash before or during the loop."""
    return {
        "stop_reason": "infra_error",
        "turns": 0,
        "seconds": 0.0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "tool_calls": 0,
        "malformed_tool_calls": 0,
        "error": detail,
    }


def used_settings(agent: Agent, config: dict) -> dict:
    """Find the digest, context size, and temperature that the run used."""
    used = {"model_digest": None, "num_ctx": config["num_ctx"], "temperature": config["temperature"]}
    try:
        used["model_digest"] = agent.model.digest()
        if used["num_ctx"] is None:
            used["num_ctx"] = agent.model.loaded_context_length()
        if used["temperature"] is None:
            raw = agent.model.default_parameters().get("temperature")
            used["temperature"] = float(raw) if raw is not None else None
    except Exception as error:
        print(f"could not read the model settings: {error}", file=sys.stderr)
    return used


def write_result(path: str, config: dict, run: dict, used: dict, exit_code: int) -> None:
    """Write result.json with exactly the keys in the spec."""
    result_path = Path(path)
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "config_id": config_id(config),
        "task": result_path.parent.parent.name,
        "trial": trial_number(result_path.parent.name),
        "stop_reason": run["stop_reason"],
        "turns": run["turns"],
        "seconds": run["seconds"],
        "prompt_tokens": run["prompt_tokens"],
        "completion_tokens": run["completion_tokens"],
        "model": config["model"],
        "model_digest": used["model_digest"],
        "num_ctx": used["num_ctx"],
        "temperature": used["temperature"],
        "think": config["think"],
        "exit_code": exit_code,
        "tool_calls": run["tool_calls"],
        "malformed_tool_calls": run["malformed_tool_calls"],
        "passed": None,
        "grader_output": None,
    }
    result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def trial_number(name: str) -> int | None:
    """Read the trial number from the trial folder name, or None if it is not a number."""
    return int(name) if name.isdigit() else None


def run_chat(args: argparse.Namespace) -> int:
    """Read user lines from stdin. Each line runs the loop on the shared history."""
    config = load_config(args.config)
    agent = build_agent(config, args.workdir)
    messages = [{"role": "system", "content": agent.system_prompt}]
    print(f"{config_id(config)} in {args.workdir}. Type exit to stop.")
    agent.env.start()
    try:
        while True:
            try:
                line = input("> ")
            except EOFError:
                break
            if line.strip() == "exit":
                break
            if not line.strip():
                continue
            messages.append({"role": "user", "content": line})
            run = run_loop(agent.model, agent.tools, messages, agent.max_turns, agent.max_seconds, print_record)
            if run["stop_reason"] == "infra_error":
                print(run["error"], file=sys.stderr)
                return 3
    finally:
        agent.env.stop()
    return 0


def print_record(entry: dict) -> None:
    """Show one transcript record to the person at the terminal."""
    kind = entry["type"]
    if kind == "assistant":
        if entry.get("thinking"):
            print(f"[thinking: {len(entry['thinking'])} characters]")
        if entry["content"]:
            print(entry["content"])
        for call in entry.get("tool_calls", []):
            print(f"-> {call['name']} {json.dumps(call['arguments'], ensure_ascii=False)}")
    elif kind == "tool_result":
        preview = entry["content"]
        if len(preview) > RESULT_PREVIEW_CHARS:
            preview = preview[:RESULT_PREVIEW_CHARS] + "..."
        print(f"<- {entry['name']}: {preview}")
    elif kind == "end":
        print(f"[{entry['stop_reason']}, {entry['turns']} turns, {entry['seconds']} s]")
    sys.stdout.flush()


if __name__ == "__main__":
    sys.exit(main())
