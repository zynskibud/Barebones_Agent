"""The cloud env: runs in an E2B cloud sandbox (a Firecracker microVM).

This is part of the env seam (a behavior seam).
Tools call this module and never touch the sandbox directly.

The harness and the model stay on this machine. Only the tools act in the sandbox.
There is no shared folder, so the sandbox copy is the single source of truth
while the agent works:

- start() creates the sandbox and uploads the host working folder to WORK_ROOT.
- read, write, list, and run act on the sandbox copy only.
- stop() downloads WORK_ROOT back into the host working folder, so that the
  eval harness can grade it on the host, and then kills the sandbox.

safe_path is pure path logic: it normalizes the path against WORK_ROOT and
rejects any path that leaves it. It does not follow symlinks, because there is
no host folder to resolve against. The sandbox is the boundary. The host is
protected at stop(): the download is extracted with the tarfile data filter,
so no member can land outside the host working folder.

The E2B SDK is imported inside the methods. build.py imports this module for
every run, and the other envs must not load the SDK.

The API key comes from E2B_API_KEY in the environment, or else from the
E2B_API_KEY line in .env at the repo root. This module never prints it.
"""

import io
import os
import posixpath
import shlex
import shutil
import sys
import tarfile
import tempfile
import time
from pathlib import Path

from env.base import Env, IsDirectory, NotDirectory, NotFound, OutsideFolder, Timeout

REPO_ROOT = Path(__file__).resolve().parents[4]
WORK_ROOT = "/home/user/work"
UPLOAD_ARCHIVE = "/tmp/barebones-upload.tar.gz"
DOWNLOAD_ARCHIVE = "/tmp/barebones-download.tar.gz"
# The env does not get max_seconds (build.py passes only the working folder).
# 900 s is above max_seconds (600) plus the eval harness grace (60). If the
# harness is killed before stop(), E2B kills the sandbox at this timeout.
SANDBOX_SECONDS = 900
# The commands that the env runs for itself (setup, upload, download, checks) get this timeout.
SETUP_SECONDS = 120
# The default E2B template has Python 3.11 and no pytest. This installs the
# pytest version from uv.lock until a custom template holds the toolchains.
SETUP_COMMAND = "pip install --quiet --disable-pip-version-check pytest==9.1.1"
METADATA = {"app": "barebones-agent"}


class CloudEnv(Env):
    """Files and commands in one E2B sandbox, inside one working folder."""

    def __init__(self, workdir: str) -> None:
        super().__init__(workdir)
        self.host_root = Path(workdir).resolve()
        if not self.host_root.is_dir():
            raise FileNotFoundError(f"the working folder {workdir} does not exist")
        self.sandbox = None
        self.refreshed = 0.0

    def start(self) -> None:
        """Create the sandbox, upload the working folder, and install pytest."""
        from e2b import Sandbox

        if self.sandbox is not None:
            return
        self.sandbox = Sandbox.create(timeout=SANDBOX_SECONDS, metadata=METADATA, api_key=api_key())
        self.refreshed = time.monotonic()
        try:
            self.upload()
            self.sandbox.commands.run(SETUP_COMMAND, user="root", timeout=SETUP_SECONDS)
        except BaseException:
            # main.py calls stop() only after start() returns, so clean up here.
            self.kill()
            raise

    def stop(self) -> None:
        """Download the working folder to the host, then kill the sandbox. Safe to call twice."""
        if self.sandbox is None:
            return
        try:
            self.download()
        finally:
            self.kill()

    def safe_path(self, path: str) -> str:
        """Return the sandbox path under WORK_ROOT. Raise OutsideFolder if it leaves."""
        target = posixpath.normpath(posixpath.join(WORK_ROOT, path))
        if target != WORK_ROOT and not target.startswith(WORK_ROOT + "/"):
            raise OutsideFolder(path)
        return target

    def read(self, path: str) -> str:
        from e2b import FileNotFoundException, SandboxException

        target = self.safe_path(path)
        self.keep_alive()
        try:
            data = self.sandbox.files.read(target, format="bytes")
        except FileNotFoundException:
            raise NotFound(path) from None
        except SandboxException:
            kind = self.kind(target)
            if kind == "dir":
                raise IsDirectory(path) from None
            if kind is None:
                raise NotFound(path) from None
            raise
        return bytes(data).decode("utf-8", errors="replace")

    def write(self, path: str, text: str) -> None:
        target = self.safe_path(path)
        self.keep_alive()
        # The sandbox creates the parent folders.
        self.sandbox.files.write(target, text.encode("utf-8"))

    def list(self, path: str) -> list[str]:
        from e2b import FileNotFoundException, FileType, SandboxException

        target = self.safe_path(path)
        self.keep_alive()
        try:
            entries = self.sandbox.files.list(target, depth=1)
        except FileNotFoundException:
            raise NotFound(path) from None
        except SandboxException:
            kind = self.kind(target)
            if kind is None:
                raise NotFound(path) from None
            if kind != "dir":
                raise NotDirectory(path) from None
            raise
        entries = sorted(entries, key=lambda entry: entry.name)
        return [entry.name + "/" if entry.type == FileType.DIR else entry.name for entry in entries]

    def run(self, command: str, timeout: float) -> tuple[str, str, int]:
        from e2b import CommandExitException, TimeoutException

        self.keep_alive()
        # E2B runs every command as /bin/bash -l -c <cmd> in the process group
        # of its daemon. exec setsid gives bash -c its own process group, with
        # the group id equal to the handle pid, so that a timeout can kill the group.
        wrapped = "exec setsid bash -c " + shlex.quote(command)
        handle = self.sandbox.commands.run(wrapped, background=True, cwd=WORK_ROOT, timeout=timeout)
        try:
            result = handle.wait()
        except CommandExitException as error:
            return error.stdout, error.stderr, error.exit_code
        except TimeoutException:
            # The E2B timeout ends the stream only. The command keeps running.
            self.kill_group(handle.pid)
            raise Timeout(command) from None
        return result.stdout, result.stderr, result.exit_code

    def upload(self) -> None:
        """Copy every file under the host working folder to WORK_ROOT."""
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            archive.add(self.host_root, arcname=".")
        self.sandbox.files.write(UPLOAD_ARCHIVE, buffer.getvalue())
        self.sandbox.commands.run(
            f"mkdir -p {WORK_ROOT} && tar -xzf {UPLOAD_ARCHIVE} -C {WORK_ROOT} && rm {UPLOAD_ARCHIVE}",
            timeout=SETUP_SECONDS,
        )

    def download(self) -> None:
        """Replace the host working folder contents with WORK_ROOT.

        Host files that the agent deleted in the sandbox are deleted on the host.
        The host folder changes only after the whole archive is extracted.
        """
        self.sandbox.commands.run(
            f"tar -czf {DOWNLOAD_ARCHIVE} -C {WORK_ROOT} .", user="root", timeout=SETUP_SECONDS
        )
        data = bytes(self.sandbox.files.read(DOWNLOAD_ARCHIVE, format="bytes", user="root"))
        staging = Path(tempfile.mkdtemp(prefix="barebones-download-"))
        try:
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
                archive.extractall(staging, filter=host_filter)
            for entry in list(self.host_root.iterdir()):
                remove(entry)
            for entry in list(staging.iterdir()):
                shutil.move(str(entry), str(self.host_root / entry.name))
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def kind(self, target: str) -> str | None:
        """Return "dir", "file", or None when the sandbox path does not exist.

        Only the error paths call this. A shell test follows symlinks like the
        local env, and it answers for every path (for example a path under a
        file, where the E2B file API gives an internal error).
        """
        quoted = shlex.quote(target)
        result = self.sandbox.commands.run(
            f"if [ -d {quoted} ]; then echo dir; elif [ -e {quoted} ]; then echo file; fi",
            timeout=SETUP_SECONDS,
        )
        return result.stdout.strip() or None

    def kill_group(self, pid: int) -> None:
        """Kill the command and every process in its group."""
        from e2b import CommandExitException

        try:
            self.sandbox.commands.run(f"kill -9 -- -{pid}", timeout=SETUP_SECONDS)
        except CommandExitException:
            # The group ended on its own.
            pass

    def keep_alive(self) -> None:
        """Push the sandbox timeout forward when half of it has passed (for long chats)."""
        now = time.monotonic()
        if now - self.refreshed > SANDBOX_SECONDS / 2:
            self.sandbox.set_timeout(SANDBOX_SECONDS)
            self.refreshed = now

    def kill(self) -> None:
        """Kill the sandbox and forget it.

        A failed kill does not fail the run: the work is already on the host,
        and E2B kills the sandbox at SANDBOX_SECONDS.
        """
        sandbox, self.sandbox = self.sandbox, None
        if sandbox is None:
            return
        try:
            sandbox.kill()
        except Exception as error:
            print(f"cloud env: could not kill sandbox {sandbox.sandbox_id}: {error}", file=sys.stderr)


def host_filter(member: tarfile.TarInfo, dest: str) -> tarfile.TarInfo | None:
    """Apply the tarfile data filter. Skip a member that it rejects, and say so on stderr."""
    try:
        return tarfile.data_filter(member, dest)
    except tarfile.FilterError as error:
        print(f"cloud env: skipped {member.name} in the download: {error}", file=sys.stderr)
        return None


def remove(path: Path) -> None:
    """Delete a file, a symlink, or a folder tree."""
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def api_key() -> str:
    """Return E2B_API_KEY from the environment, or else from .env at the repo root."""
    key = os.environ.get("E2B_API_KEY")
    if key:
        return key
    env_file = REPO_ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            name, separator, value = line.partition("=")
            if separator and name.strip() == "E2B_API_KEY":
                return value.strip().strip("'\"")
    raise RuntimeError("E2B_API_KEY is not set. Set it in the environment or in .env at the repo root.")
