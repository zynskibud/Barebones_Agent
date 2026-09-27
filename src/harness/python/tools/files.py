"""The file tools: read_file, list_files, edit_file.

This is part of the tools seam (a behavior seam).
Each tool calls env, never the machine directly.

edit_file has two error modes, chosen by the tool_errors setting:

- plain (default, absent, or null): today's behavior, byte-identical.
- rich: the plain error string, plus candidate lines from the file, to give
  the model something to act on instead of repeating the same failed call.
"""

import difflib

from env.base import Env, EnvError, NotFound
from tools.bash import TIMEOUT_SECONDS, with_newline
from tools.registry import env_error, text

MAX_CANDIDATES = 3
MAX_MATCH_LINES = 5


def read_file(env: Env, messages: dict, arguments: dict, settings: dict) -> str:
    """Return the text of one file. settings is unused: read_file has no rich mode."""
    path = arguments["path"]
    try:
        return env.read(path)
    except EnvError as error:
        return env_error(messages, error, path)


def list_files(env: Env, messages: dict, arguments: dict, settings: dict) -> str:
    """Return the names in one folder, one per line. Not recursive. Dotfiles are hidden.

    settings is unused: list_files has no rich mode.
    """
    path = arguments.get("path", ".")
    try:
        names = env.list(path)
    except EnvError as error:
        return env_error(messages, error, path)
    return "\n".join(name for name in names if not name.startswith("."))


def edit_file(env: Env, messages: dict, arguments: dict, settings: dict) -> str:
    """Replace old_str once in a file, or create the file when old_str is empty.

    settings["tool_errors"] picks plain or rich errors (lever 1). settings["auto_check"],
    when set, is a shell command that a successful edit runs, with its output appended
    to the result (lever 2). A failed edit never runs auto_check.
    """
    path = arguments["path"]
    old = arguments["old_str"]
    new = arguments["new_str"]
    rich = settings.get("tool_errors") == "rich"
    auto_check = settings.get("auto_check")
    try:
        if old == "":
            result, ok = create_file(env, messages, path, new)
        else:
            current = env.read(path)
            count = current.count(old)
            if count == 0:
                return not_found_result(messages, current, old, path, rich)
            if count > 1:
                return multiple_result(messages, current, old, path, rich)
            env.write(path, current.replace(old, new, 1))
            result, ok = text(messages, "ok.edited", path=path), True
    except EnvError as error:
        return env_error(messages, error, path)
    if ok and auto_check:
        result = result + "\n\n" + run_check(env, messages, auto_check)
    return result


def create_file(env: Env, messages: dict, path: str, content: str) -> tuple[str, bool]:
    """Create a file that does not exist yet. Return the result text and whether it was created."""
    try:
        env.read(path)
    except NotFound:
        env.write(path, content)
        return text(messages, "ok.created", path=path), True
    return text(messages, "errors.already_exists", path=path), False


def run_check(env: Env, messages: dict, command: str) -> str:
    """Run the auto_check command. Return the label, then the output in the bash shape."""
    label = text(messages, "auto_check_label", command=command)
    try:
        stdout, stderr, code = env.run(command, TIMEOUT_SECONDS)
    except EnvError as error:
        return label + "\n" + env_error(messages, error)
    return label + "\n" + with_newline(stdout) + with_newline(stderr) + text(messages, "exit_code", n=code)


def not_found_result(messages: dict, current: str, old: str, path: str, rich: bool) -> str:
    """Return the old_str_not_found error, with candidate lines when rich is on."""
    base = text(messages, "errors.old_str_not_found", path=path)
    if not rich:
        return base
    block = candidates_block(messages, current, old)
    if block is None:
        return base
    return base + "\n\n" + block


def multiple_result(messages: dict, current: str, old: str, path: str, rich: bool) -> str:
    """Return the old_str_multiple error, with the matching line numbers when rich is on."""
    base = text(messages, "errors.old_str_multiple", path=path)
    if not rich:
        return base
    lines = match_lines(current, old, MAX_MATCH_LINES)
    header = text(messages, "rich.matches_at_lines")
    return base + "\n" + header + " " + ", ".join(str(number) for number in lines)


def candidates_block(messages: dict, current: str, old: str) -> str | None:
    """Return the 'closest matches' block, or None when the file has no lines."""
    regions = closest_regions(current, first_line(old), MAX_CANDIDATES)
    if not regions:
        return None
    out = [text(messages, "rich.closest_matches")]
    for index, region in enumerate(regions):
        if index > 0:
            out.append("")
        out.extend(format_candidate_line(number, line) for number, line in region)
    return "\n".join(out)


def format_candidate_line(number: int, line: str) -> str:
    """Format one candidate line as 'N: text', or 'N:' when the line is empty."""
    if line == "":
        return f"{number}:"
    return f"{number}: {line}"


def first_line(text_block: str) -> str:
    """Return the first line of a string. An empty string has an empty first line."""
    lines = text_block.splitlines()
    return lines[0] if lines else ""


def closest_regions(current: str, target: str, limit: int) -> list[list[tuple[int, str]]]:
    """Return up to `limit` regions of the file, best-matching line first.

    Each region is the best-matching line and one line on each side that
    exists in the file, as (1-based line number, line text) pairs. Lines are
    ranked by difflib.SequenceMatcher ratio against target. Ties keep the
    earlier line. A candidate whose region shares a line with a region
    already chosen is skipped, so the same text never appears twice.
    """
    lines = current.splitlines()
    ranked = sorted(
        range(len(lines)),
        key=lambda index: (-difflib.SequenceMatcher(None, target, lines[index]).ratio(), index),
    )
    regions = []
    used: set[int] = set()
    for center in ranked:
        if len(regions) >= limit:
            break
        start = max(0, center - 1)
        end = min(len(lines) - 1, center + 1)
        window = range(start, end + 1)
        if used.intersection(window):
            continue
        regions.append([(row + 1, lines[row]) for row in window])
        used.update(window)
    return regions


def match_lines(current: str, old: str, limit: int) -> list[int]:
    """Return the 1-based line number where each occurrence of old starts.

    Occurrences are found the way str.count finds them: left to right,
    non-overlapping. Returns at most `limit` line numbers.
    """
    found = []
    start = 0
    while len(found) < limit:
        index = current.find(old, start)
        if index == -1:
            break
        found.append(current.count("\n", 0, index) + 1)
        start = index + len(old)
    return found
