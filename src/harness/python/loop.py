"""The agent loop.

Send the messages to the model, run the tool calls it asks for,
add the results, and repeat until the model stops or a limit is hit.
"""

import json
import time
from collections.abc import Callable

from model import Model, ModelError, ModelTimeout
from tools.registry import Tools

MAX_MALFORMED = 3
# The smallest HTTP timeout for one model call, in seconds.
MIN_CALL_SECONDS = 1.0

Record = Callable[[dict], None]


def run_loop(
    model: Model,
    tools: Tools,
    messages: list[dict],
    max_turns: int,
    max_seconds: float,
    record: Record,
) -> dict:
    """Run the loop from the spec on messages, in place. Return the facts of the run.

    record gets one transcript record per assistant message, tool result, and end.
    """
    turn = 0
    malformed = 0
    tool_calls = 0
    prompt_tokens = 0
    completion_tokens = 0
    error = None
    started = time.monotonic()
    while True:
        # Each call gets the time that remains, so the run ends near max_seconds.
        remaining = max(max_seconds - (time.monotonic() - started), MIN_CALL_SECONDS)
        try:
            response = model.chat(messages, tools.definitions, timeout=remaining)
        except ModelTimeout:
            stop_reason = "max_seconds"
            break
        except ModelError as failure:
            error = str(failure)
            stop_reason = "infra_error"
            break
        turn += 1
        prompt_tokens += response.get("prompt_eval_count", 0)
        completion_tokens += response.get("eval_count", 0)
        assistant = response["message"]
        messages.append(assistant)
        calls = read_tool_calls(assistant, turn)
        record(assistant_record(assistant, calls))
        if not calls:
            stop_reason = "end_turn"
            break
        for call_id, name, arguments in calls:
            content, bad = tools.call(name, arguments)
            tool_calls += 1
            malformed += int(bad)
            messages.append({"role": "tool", "tool_call_id": call_id, "tool_name": name, "content": content})
            record({"type": "tool_result", "tool_call_id": call_id, "name": name, "content": content})
        if malformed >= MAX_MALFORMED:
            stop_reason = "malformed_tool_call"
            break
        if turn >= max_turns:
            stop_reason = "max_turns"
            break
        if time.monotonic() - started >= max_seconds:
            stop_reason = "max_seconds"
            break
    seconds = round(time.monotonic() - started, 1)
    end = {"type": "end", "stop_reason": stop_reason, "turns": turn, "seconds": seconds}
    if error is not None:
        end["error"] = error
    record(end)
    return {
        "stop_reason": stop_reason,
        "turns": turn,
        "seconds": seconds,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "tool_calls": tool_calls,
        "malformed_tool_calls": malformed,
        "error": error,
    }


def read_tool_calls(assistant: dict, turn: int) -> list[tuple[str, str, object]]:
    """Return (id, name, arguments) for each tool call. Fill in an id when Ollama gives none."""
    calls = []
    for index, call in enumerate(assistant.get("tool_calls") or []):
        function = call.get("function") or {}
        call_id = call.get("id") or f"call_{turn}_{index}"
        name = function.get("name") or ""
        arguments = function.get("arguments", {})
        if isinstance(arguments, str):
            arguments = parse_json_or_keep(arguments)
        calls.append((call_id, name, arguments))
    return calls


def parse_json_or_keep(raw: str) -> object:
    """Parse arguments that arrived as a JSON string. Keep the string if it is not JSON."""
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def assistant_record(assistant: dict, calls: list[tuple[str, str, object]]) -> dict:
    """Build the assistant transcript record."""
    entry: dict = {"type": "assistant", "content": assistant.get("content", "")}
    if assistant.get("thinking"):
        entry["thinking"] = assistant["thinking"]
    if calls:
        entry["tool_calls"] = [
            {"id": call_id, "name": name, "arguments": arguments} for call_id, name, arguments in calls
        ]
    return entry
