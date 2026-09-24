"""The docker env: bash runs inside a Docker container.

This is part of the env seam (a behavior seam).
Tools call this module and never touch the container directly.

The container mounts the host working folder at /work. The container and
the host see the same files, so the eval harness grades the host folder.

- read, write, list: act on the host folder with the safe_path check of
  LocalEnv. bash sees the working folder as /work, so safe_path first maps
  a path that starts with /work to the working folder.
- run: docker exec bash -c <command> in /work. GNU timeout in the container
  kills the command and every process it started.
- start, stop: the container lives while its docker run client holds stdin
  open. If the harness dies, even by SIGKILL, the pipe closes, the container
  stops, and --rm removes it.

Build the image once, from the repo root: docker build -t barebones-task docker/
"""

import subprocess
import sys
import time
import uuid
from pathlib import Path

from env.base import Timeout
from env.local import LocalEnv, kill_group

IMAGE = "barebones-task"
MOUNT = "/work"
# Resource limits for every container, so that runs are comparable.
CPUS = "2"
MEMORY = "2g"
# The longest wait for one docker command and for the container to start, in seconds.
DOCKER_SECONDS = 30
POLL_SECONDS = 0.1
# How long the host waits for docker exec after the command timeout, in seconds.
EXEC_GRACE_SECONDS = 10
# timeout --signal KILL kills its whole process group, itself included,
# so docker exec exits with 128 + 9 when the command runs past the timeout.
KILLED = 137


class DockerEnv(LocalEnv):
    """Files on the host folder, commands in a container that mounts it."""

    def __init__(self, workdir: str, max_seconds: float | None = None, image: str = IMAGE) -> None:
        super().__init__(workdir, max_seconds)
        self.image = image
        self.name = f"barebones-{uuid.uuid4().hex[:12]}"
        # The docker run client. The container lives while its stdin is open.
        self.keeper: subprocess.Popen | None = None

    def safe_path(self, path: str) -> Path:
        """Map /work to the working folder, then run the LocalEnv check."""
        if path == MOUNT or path.startswith(MOUNT + "/"):
            path = "." + path[len(MOUNT):]
        return super().safe_path(path)

    def start(self) -> None:
        found = docker("image", "inspect", "--format", "{{.Id}}", self.image)
        if found.returncode != 0:
            if "No such image" in found.stderr:
                raise RuntimeError(
                    f"the docker image {self.image} does not exist. "
                    f"Build it from the repo root: docker build -t {self.image} docker/"
                )
            raise RuntimeError(f"docker failed: {last_line(found.stderr)}")
        self.keeper = subprocess.Popen(
            [
                "docker", "run", "--rm", "--interactive", "--init", "--pull", "never",
                "--name", self.name,
                "--cpus", CPUS, "--memory", MEMORY,
                "--volume", f"{self.root}:{MOUNT}", "--workdir", MOUNT,
                self.image, "cat",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        self.wait_until_running()

    def wait_until_running(self) -> None:
        """Return when the container runs. Remove it and raise if it does not start."""
        deadline = time.monotonic() + DOCKER_SECONDS
        while time.monotonic() < deadline:
            if self.keeper.poll() is not None:
                error = self.keeper.stderr.read()
                self.stop()
                raise RuntimeError(f"the container did not start: {last_line(error)}")
            state = docker("inspect", "--format", "{{.State.Running}}", self.name)
            if state.stdout.strip() == "true":
                return
            time.sleep(POLL_SECONDS)
        self.stop()
        raise RuntimeError(f"the container did not start within {DOCKER_SECONDS} seconds")

    def stop(self) -> None:
        """Remove the container. A second call does nothing."""
        keeper, self.keeper = self.keeper, None
        if keeper is None:
            return
        removed = docker("rm", "--force", self.name)
        if removed.returncode != 0 and "No such container" not in removed.stderr:
            print(f"could not remove the container {self.name}: {last_line(removed.stderr)}", file=sys.stderr)
        try:
            keeper.communicate(timeout=DOCKER_SECONDS)
        except subprocess.TimeoutExpired:
            kill_group(keeper)

    def run(self, command: str, timeout: float) -> tuple[str, str, int]:
        if self.keeper is None or self.keeper.poll() is not None:
            raise RuntimeError(f"the container {self.name} is not running")
        process = subprocess.Popen(
            ["docker", "exec", self.name, "timeout", "--signal", "KILL", f"{timeout:g}", "bash", "-c", command],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            start_new_session=True,
        )
        started = time.monotonic()
        try:
            stdout, stderr = process.communicate(timeout=timeout + EXEC_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            kill_group(process)
            raise Timeout(command) from None
        if process.returncode == KILLED and time.monotonic() - started >= timeout:
            raise Timeout(command)
        return stdout, stderr, process.returncode


def docker(*args: str) -> subprocess.CompletedProcess:
    """Run one docker command. Return the result. Never raise."""
    try:
        return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=DOCKER_SECONDS, check=False)
    except FileNotFoundError:
        return subprocess.CompletedProcess(args, 127, "", "the docker command is not on PATH")
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 1, "", f"docker {args[0]} did not answer in {DOCKER_SECONDS} seconds")


def last_line(text: str) -> str:
    """Return the last line of a docker error, or a note when there is none."""
    lines = text.strip().splitlines()
    return lines[-1] if lines else "no error text"
