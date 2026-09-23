"""The local env: runs on the laptop.

This is part of the env seam (a behavior seam). Every path goes through
a safe_path check that keeps the agent inside one working folder.
Tools call this module and never touch the disk directly.
"""

import os
import signal
import subprocess
from pathlib import Path

from env.base import Env, IsDirectory, NotDirectory, NotFound, OutsideFolder, Timeout


class LocalEnv(Env):
    """Files and commands on this machine, inside one working folder."""

    def __init__(self, workdir: str) -> None:
        super().__init__(workdir)
        self.root = Path(workdir).resolve()
        if not self.root.is_dir():
            raise FileNotFoundError(f"the working folder {workdir} does not exist")

    def safe_path(self, path: str) -> Path:
        """Resolve a path inside the working folder. Raise OutsideFolder if it leaves."""
        target = (self.root / path).resolve()
        if target != self.root and self.root not in target.parents:
            raise OutsideFolder(path)
        return target

    def read(self, path: str) -> str:
        target = self.safe_path(path)
        if target.is_dir():
            raise IsDirectory(path)
        if not target.is_file():
            raise NotFound(path)
        return target.read_text(encoding="utf-8", errors="replace")

    def write(self, path: str, text: str) -> None:
        target = self.safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def list(self, path: str) -> list[str]:
        target = self.safe_path(path)
        if not target.exists():
            raise NotFound(path)
        if not target.is_dir():
            raise NotDirectory(path)
        entries = sorted(target.iterdir(), key=lambda entry: entry.name)
        return [entry.name + "/" if entry.is_dir() else entry.name for entry in entries]

    def run(self, command: str, timeout: float) -> tuple[str, str, int]:
        process = subprocess.Popen(
            ["bash", "-c", command],
            cwd=self.root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            kill_group(process)
            raise Timeout(command) from None
        return stdout, stderr, process.returncode


def kill_group(process: subprocess.Popen) -> None:
    """Kill the command and every process it started, then release the pipes."""
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()
    if process.stdout is not None:
        process.stdout.close()
    if process.stderr is not None:
        process.stderr.close()
