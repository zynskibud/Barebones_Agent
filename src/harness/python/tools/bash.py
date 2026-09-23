"""The bash tool: run one shell command.

This is part of the tools seam (a behavior seam).
The tool calls env, never the machine directly.
"""

from env.base import Env, EnvError
from tools.registry import env_error, text

TIMEOUT_SECONDS = 30


def bash(env: Env, messages: dict, arguments: dict) -> str:
    """Run the command. Return stdout, then stderr, then the exit code line."""
    try:
        stdout, stderr, code = env.run(arguments["command"], TIMEOUT_SECONDS)
    except EnvError as error:
        return env_error(messages, error)
    return with_newline(stdout) + with_newline(stderr) + text(messages, "exit_code", n=code)


def with_newline(part: str) -> str:
    """Return the part with one newline at the end. An empty part stays empty."""
    if part == "" or part.endswith("\n"):
        return part
    return part + "\n"
