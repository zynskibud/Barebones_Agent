"""The file tools: read_file, list_files, edit_file.

This is part of the tools seam (a behavior seam).
Each tool calls env, never the machine directly.
"""

from env.base import Env, EnvError, NotFound
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


def edit_file(env: Env, messages: dict, arguments: dict) -> str:
    """Replace old_str once in a file, or create the file when old_str is empty."""
    path = arguments["path"]
    old = arguments["old_str"]
    new = arguments["new_str"]
    try:
        if old == "":
            return create_file(env, messages, path, new)
        current = env.read(path)
        count = current.count(old)
        if count == 0:
            return text(messages, "errors.old_str_not_found", path=path)
        if count > 1:
            return text(messages, "errors.old_str_multiple", path=path)
        env.write(path, current.replace(old, new, 1))
    except EnvError as error:
        return env_error(messages, error, path)
    return text(messages, "ok.edited", path=path)


def create_file(env: Env, messages: dict, path: str, content: str) -> str:
    """Create a file that does not exist yet."""
    try:
        env.read(path)
    except NotFound:
        env.write(path, content)
        return text(messages, "ok.created", path=path)
    return text(messages, "errors.already_exists", path=path)
