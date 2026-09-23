"""The cloud env: runs in a cloud sandbox.

This is part of the env seam (a behavior seam).
Tools call this module and never touch the sandbox directly.

Not built yet. Wave 3 must implement the Env interface in env/base.py:

- __init__(workdir): keep the host working folder path.
- start(): create the sandbox and upload the host working folder into it.
- read(path), write(path, text), list(path): act on files in the sandbox
  copy of the folder. Run safe_path against that copy, so that a path can
  never leave it. Raise the EnvError classes from env/base.py.
- run(command, timeout): run bash -c <command> in the sandbox copy with the
  timeout. Raise Timeout when the command runs past it.
- stop(): download the changed folder back to the host working folder, so
  that the eval harness can grade it, then delete the sandbox.
"""

from env.base import Env


class CloudEnv(Env):
    """Placeholder. Raises until wave 3 builds it."""

    def __init__(self, workdir: str) -> None:
        raise NotImplementedError("The cloud env is not built yet. Set env: local in the config.")
