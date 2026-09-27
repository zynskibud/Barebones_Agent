"""The file tools: read_file, list_files, edit_file.

This is part of the tools seam (a behavior seam).
Each tool calls env, never the machine directly.
"""

from env.base import Env, EnvError, NotFound
from tools.bash import TIMEOUT_SECONDS, with_newline
from tools.registry import env_error, text


def read_file(env: Env, messages: dict, arguments: dict) -> str:
    """Return the text of one file."""
    path = arguments["path"]
    try:
        return env.read(path)
    except EnvError as error:
        return env_error(messages, error, path)


def list_files(env: Env, messages: dict, arguments: dict) -> str:
    """Return the names in one folder, one per line. Not recursive. Dotfiles are hidden."""
    path = arguments.get("path", ".")
    try:
        names = env.list(path)
    except EnvError as error:
        return env_error(messages, error, path)
    return "\n".join(name for name in names if not name.startswith("."))


def edit_file(env: Env, messages: dict, arguments: dict, auto_check: str | None = None) -> str:
    """Replace old_str once in a file, or create the file when old_str is empty.

    auto_check is a shell command. When it is set, a successful edit runs it
    in env and appends its output to the result. A failed edit never runs it.
    """
    path = arguments["path"]
    old = arguments["old_str"]
    new = arguments["new_str"]
    try:
        if old == "":
            result, ok = create_file(env, messages, path, new)
        else:
            current = env.read(path)
            count = current.count(old)
            if count == 0:
                return text(messages, "errors.old_str_not_found", path=path)
            if count > 1:
                return text(messages, "errors.old_str_multiple", path=path)
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
