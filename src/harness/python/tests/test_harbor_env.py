"""HarborEnv behaves like LocalEnv on the same inputs.

Run: uv run python -m pytest src/harness/python/tests -q
"""

import sys
from pathlib import Path

import pytest

HARNESS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HARNESS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from env.base import IsDirectory, NotDirectory, NotFound, OutsideFolder, Timeout  # noqa: E402
from env.harbor import HarborEnv  # noqa: E402
from env.local import LocalEnv  # noqa: E402
from fake_harbor import FakeEnvironment, LoopThread  # noqa: E402

FILES = {"a.py": "print(1)\n", "pkg/b.py": "x = 2\n", ".hidden": "h\n"}


def fill(root: Path) -> None:
    """Write the same small tree into a folder."""
    for name, text in FILES.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)


@pytest.fixture
def envs(tmp_path):
    """A LocalEnv and a HarborEnv on two copies of the same tree."""
    local_root = tmp_path / "local"
    harbor_root = tmp_path / "container" / "app"
    local_root.mkdir()
    harbor_root.mkdir(parents=True)
    fill(local_root)
    fill(harbor_root)
    with LoopThread() as loop:
        fake = FakeEnvironment(harbor_root)
        yield LocalEnv(str(local_root)), HarborEnv(str(harbor_root), 300, environment=fake, loop=loop)


def outcome(call):
    """Return the value of call(), or the name of the EnvError class it raised."""
    try:
        return call()
    except (IsDirectory, NotDirectory, NotFound, OutsideFolder, Timeout) as error:
        return (type(error).__name__, error.path)


@pytest.mark.parametrize("path", ["a.py", "pkg/b.py", "./pkg/../a.py", "pkg", "missing.py", "../x", "/etc/passwd", "a.py/x"])
def test_read_matches_local(envs, path):
    local, harbor = envs
    assert outcome(lambda: harbor.read(path)) == outcome(lambda: local.read(path))


@pytest.mark.parametrize("path", [".", "pkg", "pkg/", "a.py", "missing", "../"])
def test_list_matches_local(envs, path):
    local, harbor = envs
    assert outcome(lambda: harbor.list(path)) == outcome(lambda: local.list(path))


@pytest.mark.parametrize("path", ["new.py", "deep/er/c.py", "a.py", "a.py/x", "../escape.py"])
def test_write_matches_local(envs, path):
    local, harbor = envs
    assert outcome(lambda: harbor.write(path, "y = 3\n")) == outcome(lambda: local.write(path, "y = 3\n"))
    assert outcome(lambda: harbor.read(path)) == outcome(lambda: local.read(path))


def test_write_then_list(envs):
    local, harbor = envs
    for env in envs:
        env.write("pkg/sub/d.py", "")
    assert harbor.list("pkg") == local.list("pkg") == ["b.py", "sub/"]


@pytest.mark.parametrize("command", ["echo out; echo err >&2; exit 3", "ls", "cat a.py", "pwd | wc -l"])
def test_run_matches_local(envs, command):
    local, harbor = envs
    assert harbor.run(command, 30) == local.run(command, 30)


def test_run_timeout(envs):
    local, harbor = envs
    assert outcome(lambda: harbor.run("sleep 5", 0.5)) == outcome(lambda: local.run("sleep 5", 0.5))


def test_safe_path_is_pure(envs):
    _, harbor = envs
    root = harbor.root
    assert harbor.safe_path(".") == root
    assert harbor.safe_path("x/../y") == root + "/y"
    assert harbor.safe_path(root + "/z") == root + "/z"
    with pytest.raises(OutsideFolder):
        harbor.safe_path(root + "-other/z")


def test_needs_the_environment():
    with pytest.raises(ValueError):
        HarborEnv("/app", 300)
