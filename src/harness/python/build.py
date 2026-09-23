"""The composition root.

build_agent(config) is the only place that reads the choices
and builds the parts: model, tools, env, and loop.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from env.base import Env
from env.cloud import CloudEnv
from env.docker import DockerEnv
from env.local import LocalEnv
from model import Model
from tools import bash, files
from tools.registry import Tools

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = REPO_ROOT / "config"

ENVS = {"local": LocalEnv, "docker": DockerEnv, "cloud": CloudEnv}

HANDLERS = {
    "read_file": files.read_file,
    "list_files": files.list_files,
    "edit_file": files.edit_file,
    "bash": bash.bash,
}


@dataclass
class Agent:
    """The built parts that the loop and main need."""

    model: Model
    tools: Tools
    env: Env
    system_prompt: str
    max_turns: int
    max_seconds: float


def build_agent(config: dict, workdir: str) -> Agent:
    """Read the choices in config and build every part."""
    env_class = ENVS[config["env"]]
    env = env_class(workdir)
    messages = json.loads((CONFIG_DIR / "messages.json").read_text(encoding="utf-8"))
    tools_file = json.loads((CONFIG_DIR / "tools.json").read_text(encoding="utf-8"))
    definitions = [tools_file["tools"][name] for name in tools_file["sets"][config["tools"]]]
    tools = Tools(definitions, HANDLERS, env, messages)
    model = Model(
        name=config["model"],
        think=config["think"],
        num_ctx=config["num_ctx"],
        temperature=config["temperature"],
        timeout=config["max_seconds"],
    )
    system_prompt = (CONFIG_DIR / "system_prompt.txt").read_text(encoding="utf-8").rstrip()
    return Agent(model, tools, env, system_prompt, config["max_turns"], config["max_seconds"])


def config_id(config: dict) -> str:
    """Return <harness>.<tools>.<env>.<codebase>.<model-id>.<think-id>."""
    model_id = config["model"].replace(":", "-")
    think_id = "think" if config["think"] else "no-think"
    return ".".join([config["harness"], config["tools"], config["env"], config["codebase"], model_id, think_id])


def load_config(path: str) -> dict:
    """Read a flat YAML config file: one `key: value` per line, with # comments."""
    config = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = strip_comment(line).strip()
        if not line or ":" not in line:
            continue
        key, raw = line.split(":", 1)
        config[key.strip()] = parse_scalar(raw.strip())
    return config


def strip_comment(line: str) -> str:
    """Remove a # comment. A # inside quotes stays."""
    quote = None
    for index, char in enumerate(line):
        if quote:
            if char == quote:
                quote = None
        elif char in ("'", '"'):
            quote = char
        elif char == "#" and (index == 0 or line[index - 1] in " \t"):
            return line[:index]
    return line


def parse_scalar(raw: str) -> object:
    """Turn one YAML scalar into a Python value."""
    if raw in ("", "null", "~"):
        return None
    if raw in ("true", "True"):
        return True
    if raw in ("false", "False"):
        return False
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        return raw[1:-1]
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw
