"""The docker env: runs inside a Docker container.

This is part of the env seam (a behavior seam).
Tools call this module and never touch the container directly.

Not built yet. Wave 3 must implement the Env interface in env/base.py:

- __init__(workdir): keep the host working folder path.
- start(): start a container with the host working folder mounted at one
  fixed path inside, for example /work.
- read(path), write(path, text), list(path): act on files under the mounted
  folder. Run safe_path against the mounted folder, so that a path can
  never leave it. Raise the EnvError classes from env/base.py.
- run(command, timeout): docker exec bash -c <command> in the mounted
  folder. Kill the command at the timeout and raise Timeout.
- stop(): remove the container.
"""

from env.base import Env


class DockerEnv(Env):
    """Placeholder. Raises until wave 3 builds it."""

    def __init__(self, workdir: str) -> None:
        raise NotImplementedError("The docker env is not built yet. Set env: local in the config.")
