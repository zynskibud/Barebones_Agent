"""A fake Harbor environment for the tests. No Docker, no Harbor.

The fake container root is a host temp folder. exec runs bash there, with a
small GNU timeout stand-in on PATH, because macOS has no timeout command.
upload_file copies a host file. That is the part of the Harbor
BaseEnvironment API that HarborEnv uses.
"""

import asyncio
import os
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

TIMEOUT_SHIM = """#!{python}
import subprocess, sys
args = sys.argv[1:]
if args[:1] == ["--signal"]:
    args = args[2:]
limit, command = float(args[0]), args[1:]
try:
    sys.exit(subprocess.run(command, timeout=limit).returncode)
except subprocess.TimeoutExpired:
    sys.exit(137)
"""


@dataclass
class ExecResult:
    stdout: str | None
    stderr: str | None
    return_code: int


class FakeEnvironment:
    """The Harbor environment calls that HarborEnv makes, on a host folder."""

    def __init__(self, root: Path, workdir: str | None = None) -> None:
        self.root = root
        self.bin = root.parent / "fake-bin"
        self.bin.mkdir(exist_ok=True)
        shim = self.bin / "timeout"
        shim.write_text(TIMEOUT_SHIM.format(python=sys.executable))
        shim.chmod(0o755)
        self.task_env_config = type("Config", (), {"workdir": workdir})()
        self.commands: list[str] = []

    async def exec(self, command, cwd=None, env=None, timeout_sec=None, user=None):
        self.commands.append(command)
        variables = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}")
        done = await asyncio.to_thread(
            subprocess.run,
            ["bash", "-c", command],
            cwd=cwd or self.root,
            env=variables,
            capture_output=True,
            text=True,
            errors="replace",
            stdin=subprocess.DEVNULL,
            timeout=timeout_sec,
        )
        return ExecResult(done.stdout, done.stderr, done.returncode)

    async def upload_file(self, source_path, target_path):
        shutil.copyfile(source_path, target_path)


class LoopThread:
    """An event loop in a background thread, like Harbor's loop while the harness thread works."""

    def __enter__(self) -> asyncio.AbstractEventLoop:
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()
        return self.loop

    def __exit__(self, *details) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join()
        self.loop.close()
