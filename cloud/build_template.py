"""Build the E2B template for env: cloud. One template holds the three task toolchains.

Run it from the repo root, once:

    uv run python cloud/build_template.py

It needs E2B_API_KEY in the environment or in .env at the repo root. It never prints the key.
The versions match docker/Dockerfile. To change a version, edit the constant and build again.
This script is tooling, like docker/Dockerfile. The harness itself imports e2b only in
src/harness/python/env/cloud.py.
"""

import os
import sys
from pathlib import Path

from e2b import Template

REPO_ROOT = Path(__file__).resolve().parents[1]
NAME = "barebones-agent"
PYTHON_IMAGE = "python:3.12.14-slim-trixie"
PYTEST_VERSION = "9.1.1"
NODE_VERSION = "24.21.0"
RUST_VERSION = "1.98.1"
CPU_COUNT = 2
MEMORY_MB = 2048
RUSTUP_HOME = "/usr/local/rustup"
CARGO_HOME = "/usr/local/cargo"
# E2B sandboxes run on x86_64.
NODE_URL = f"https://nodejs.org/dist/v{NODE_VERSION}/node-v{NODE_VERSION}-linux-x64.tar.xz"
TOOLCHAIN_BIN = f"{RUSTUP_HOME}/toolchains/{RUST_VERSION}-x86_64-unknown-linux-gnu/bin"


def template():
    """Return the template: Python 3.12 with pytest, Node 24, and Rust stable minimal."""
    return (
        Template()
        .from_image(PYTHON_IMAGE)
        .set_envs({"PIP_ROOT_USER_ACTION": "ignore", "RUSTUP_HOME": RUSTUP_HOME, "CARGO_HOME": CARGO_HOME})
        # rustc links through cc, so the image needs gcc and the C library headers.
        .apt_install(
            ["gcc", "libc6-dev", "procps", "curl", "ca-certificates", "xz-utils"],
            no_install_recommends=True,
        )
        .run_cmd(f"pip install --no-cache-dir pytest=={PYTEST_VERSION}", user="root")
        # Node: the official binary tarball, unpacked over /usr/local.
        .run_cmd(f"curl -fsSL {NODE_URL} | tar -xJ -C /usr/local --strip-components=1", user="root")
        # Rust: rustup with the minimal profile (rustc, cargo, std) in a shared folder.
        .run_cmd(
            "curl -fsSL https://sh.rustup.rs | sh -s -- -y --profile minimal "
            f"--default-toolchain {RUST_VERSION} --no-modify-path",
            user="root",
        )
        # The real toolchain binaries go on the PATH of every user. rustc finds its
        # sysroot from its own real path, so it needs no RUSTUP_HOME at run time.
        .run_cmd(
            f"ln -s {TOOLCHAIN_BIN}/cargo {TOOLCHAIN_BIN}/rustc {TOOLCHAIN_BIN}/rustdoc /usr/local/bin/",
            user="root",
        )
        .run_cmd(f"chmod -R a+rX {RUSTUP_HOME} {CARGO_HOME}", user="root")
        .set_workdir("/home/user")
    )


def log(entry) -> None:
    """Print one build log line."""
    level = getattr(entry, "level", "")
    message = getattr(entry, "message", entry)
    print(f"{level}: {message}".rstrip(), flush=True)


def load_api_key() -> None:
    """Put E2B_API_KEY from .env into the environment when it is not set."""
    if os.environ.get("E2B_API_KEY"):
        return
    env_file = REPO_ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            name, separator, value = line.partition("=")
            if separator and name.strip() == "E2B_API_KEY":
                os.environ["E2B_API_KEY"] = value.strip().strip("'\"")
                return
    sys.exit("E2B_API_KEY is not set. Set it in the environment or in .env at the repo root.")


def main() -> int:
    load_api_key()
    info = Template.build(template(), NAME, cpu_count=CPU_COUNT, memory_mb=MEMORY_MB, on_build_logs=log)
    print(f"built template {NAME}: {info}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
