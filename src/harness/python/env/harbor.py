"""The harbor env: the tools act in a Harbor task environment.

This is part of the env seam (a behavior seam).
Tools call this module and never touch the Harbor environment directly.

Harbor (https://github.com/harbor-framework/harbor) starts each benchmark
task in its own container and hands the agent a BaseEnvironment object. The
harness and the model stay on this machine. Only the tools act in the
container, as in the docker and cloud envs. Harbor starts and stops the
container, and Harbor grades it, so start() and stop() do nothing here.

The Harbor API is async. The agent loop is sync and runs in a worker thread.
Each method sends one coroutine to Harbor's event loop and waits for it.

- workdir is the container work root (the task WORKDIR, for example /app).
- safe_path is pure path logic, as in the cloud env: it normalizes the path
  against the work root and rejects any path that leaves it. It does not
  follow symlinks. The container is the boundary.
- read, list: one environment.exec call each, with a shell test for the
  folder and missing-file cases.
- write: mkdir -p through exec, then environment.upload_file from a host
  temp file. A parent that is a file gives NotDirectory.
- run: environment.exec in the work root, wrapped in GNU timeout, as in the
  docker env. Harbor's own timeout_sec is a backstop.

Known differences from LocalEnv:
- read decodes the bytes that exec returns. Harbor decodes them, so invalid
  UTF-8 becomes replacement characters, as in LocalEnv.
- upload_file can create the file as the container's root user, not as the
  task's default user. The task's tests run as root in Terminal-Bench, so
  this is harmless there.
- The container image must have bash and GNU timeout (coreutils).
"""

import asyncio
import posixpath
import shlex
import tempfile
import time
from pathlib import Path

from env.base import Env, IsDirectory, NotDirectory, NotFound, OutsideFolder, Timeout

# The exit codes that the read and list shell tests use for their cases.
CODE_NOT_FOUND = 90
CODE_IS_DIRECTORY = 91
CODE_NOT_DIRECTORY = 92
# The commands that the env runs for itself (checks, mkdir) get this timeout.
SETUP_SECONDS = 60
# How long the host waits for exec after the command timeout, in seconds.
EXEC_GRACE_SECONDS = 10
# timeout --signal KILL exits with 128 + 9 when the command runs past the timeout.
KILLED = 137


class HarborEnv(Env):
    """Files and commands in one Harbor task environment, inside one work root."""

    def __init__(
        self,
        workdir: str,
        max_seconds: float | None = None,
        environment=None,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        super().__init__(workdir, max_seconds)
        if environment is None or loop is None:
            raise ValueError("the harbor env needs the Harbor environment and its event loop")
        self.root = posixpath.normpath(workdir)
        self.environment = environment
        self.loop = loop

    def call(self, coroutine):
        """Run one Harbor coroutine on Harbor's event loop and return its result."""
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop).result()

    def exec(self, command: str, timeout: float = SETUP_SECONDS):
        """Run one command in the work root. Return Harbor's ExecResult."""
        return self.call(self.environment.exec(command, cwd=self.root, timeout_sec=int(timeout)))

    def safe_path(self, path: str) -> str:
        """Return the container path under the work root. Raise OutsideFolder if it leaves."""
        target = posixpath.normpath(posixpath.join(self.root, path))
        if target != self.root and not target.startswith(self.root.rstrip("/") + "/"):
            raise OutsideFolder(path)
        return target

    def read(self, path: str) -> str:
        target = shlex.quote(self.safe_path(path))
        result = self.exec(
            f"if [ -d {target} ]; then exit {CODE_IS_DIRECTORY}; fi; "
            f"if [ ! -f {target} ]; then exit {CODE_NOT_FOUND}; fi; cat {target}"
        )
        if result.return_code == CODE_IS_DIRECTORY:
            raise IsDirectory(path)
        if result.return_code != 0:
            raise NotFound(path)
        return result.stdout or ""

    def write(self, path: str, text: str) -> None:
        target = self.safe_path(path)
        parent = shlex.quote(posixpath.dirname(target))
        made = self.exec(f"mkdir -p {parent}")
        if made.return_code != 0:
            raise NotDirectory(path, path=self.file_prefix(path))
        if self.kind(target) == "dir":
            raise IsDirectory(path)
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "upload"
            source.write_text(text, encoding="utf-8")
            self.call(self.environment.upload_file(source, target))

    def file_prefix(self, path: str) -> str:
        """Return the first prefix of path that is a file, spelled as the model sent it."""
        parts = path.split("/")
        for count in range(1, len(parts)):
            prefix = "/".join(parts[:count])
            if not prefix:
                continue
            try:
                candidate = self.safe_path(prefix)
            except OutsideFolder:
                continue
            if self.kind(candidate) == "file":
                return prefix
        return path

    def kind(self, target: str) -> str | None:
        """Return "dir", "file", or None for a container path."""
        quoted = shlex.quote(target)
        result = self.exec(f"if [ -d {quoted} ]; then echo dir; elif [ -e {quoted} ]; then echo file; fi")
        answer = (result.stdout or "").strip()
        return answer or None

    def list(self, path: str) -> list[str]:
        target = shlex.quote(self.safe_path(path))
        result = self.exec(
            f"if [ ! -e {target} ]; then exit {CODE_NOT_FOUND}; fi; "
            f"if [ ! -d {target} ]; then exit {CODE_NOT_DIRECTORY}; fi; "
            f"cd {target} && ls -A -L -p -1"
        )
        if result.return_code == CODE_NOT_FOUND:
            raise NotFound(path)
        if result.return_code == CODE_NOT_DIRECTORY:
            raise NotDirectory(path)
        names = [line for line in (result.stdout or "").splitlines() if line]
        return sorted(names, key=lambda name: name.rstrip("/"))

    def run(self, command: str, timeout: float) -> tuple[str, str, int]:
        wrapped = f"timeout --signal KILL {timeout:g} bash -c {shlex.quote(command)}"
        started = time.monotonic()
        try:
            result = self.exec(wrapped, timeout=timeout + EXEC_GRACE_SECONDS)
        except RuntimeError as error:
            if "timed out" in str(error):
                raise Timeout(command) from None
            raise
        if result.return_code == KILLED and time.monotonic() - started >= timeout:
            raise Timeout(command)
        return result.stdout or "", result.stderr or "", result.return_code
