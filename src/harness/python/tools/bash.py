"""The bash tool: run one shell command.

This is part of the tools seam (a behavior seam).
The tool calls env, never the machine directly.
"""

from env.base import Env, EnvError
from tools.registry import env_error, text

TIMEOUT_SECONDS = 30


def bash(env: Env, messages: dict, arguments: dict, settings: dict) -> str:
    """Run the command. Return stdout, then stderr, then the exit code line.

    settings["bash_timeout"] is the command timeout in seconds. If it is absent or
    null, the timeout is TIMEOUT_SECONDS.
    """
    timeout = settings.get("bash_timeout")
    if timeout is None:
        timeout = TIMEOUT_SECONDS
    try:
        stdout, stderr, code = env.run(arguments["command"], timeout)
    except EnvError as error:
        return env_error(messages, error, seconds=timeout)
    return with_newline(stdout) + with_newline(stderr) + text(messages, "exit_code", n=code)


def with_newline(part: str) -> str:
    """Return the part with one newline at the end. An empty part stays empty."""
    if part == "" or part.endswith("\n"):
        return part
    return part + "\n"
