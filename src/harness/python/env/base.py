"""The Env interface: what every environment offers the tools.

An env is the place where the tools act: the laptop, a Docker container,
or a cloud sandbox. The tools call the methods below and nothing else.

Every env receives the host working folder path. The env is responsible
for making that folder visible to itself, for example by mounting it.

Paths are the strings that the model sent. The env resolves each path and
keeps it inside the working folder. When a path or a command has a problem,
the env raises one of the EnvError classes below. Each class names the key
in config/messages.json that the tool returns to the model.
"""


class EnvError(Exception):
    """A problem that the tool reports to the model as text."""

    key = "errors.not_found"


class OutsideFolder(EnvError):
    """The resolved path is outside the working folder."""

    key = "errors.outside_folder"


class NotFound(EnvError):
    """The path does not exist."""

    key = "errors.not_found"


class IsDirectory(EnvError):
    """The path is a folder, and the tool needs a file."""

    key = "errors.is_directory"


class NotDirectory(EnvError):
    """The path is a file, and the tool needs a folder."""

    key = "errors.not_a_directory"


class Timeout(EnvError):
    """The command ran past the timeout."""

    key = "errors.timeout"


class Env:
    """The interface. Each env subclasses it and fills in every method."""

    def __init__(self, workdir: str) -> None:
        self.workdir = workdir

    def start(self) -> None:
        """Set up the env. A no-op for envs that need no setup."""

    def stop(self) -> None:
        """Tear down the env. A no-op for envs that need no teardown."""

    def read(self, path: str) -> str:
        """Return the text of a file. Raise NotFound or IsDirectory."""
        raise NotImplementedError

    def write(self, path: str, text: str) -> None:
        """Write text to a file. Create the file and its parent folders if needed."""
        raise NotImplementedError

    def list(self, path: str) -> list[str]:
        """Return the sorted names in a folder. Folder names end with /."""
        raise NotImplementedError

    def run(self, command: str, timeout: float) -> tuple[str, str, int]:
        """Run a shell command in the working folder. Return (stdout, stderr, exit code)."""
        raise NotImplementedError
