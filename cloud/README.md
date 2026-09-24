# The cloud env template

`env: cloud` runs the `bash` tool in an E2B sandbox made from the template `barebones-agent`.
The harness does not build the template. Build it once, from the repo root:

```
uv run python cloud/build_template.py
```

The script needs `E2B_API_KEY` in the environment or in `.env` at the repo root. It never prints the key.
A build takes about one minute. If the template does not exist, the harness stops with `infra_error`.

## What the template holds

| Part | Version | Source |
|---|---|---|
| Base | Debian 13 (trixie), slim, x86_64 | `python:3.12.14-slim-trixie` |
| Python | 3.12.14, with `python` and `python3` | the base image |
| pytest | 9.1.1, the eval harness version | pip |
| Node | 24.21.0, with npm | the official Linux x64 tarball, unpacked over `/usr/local` |
| Rust | 1.98.1 (rustc, cargo, rustdoc; minimal profile) | rustup into `/usr/local/rustup`, linked into `/usr/local/bin` |
| C linker | gcc and libc6-dev, for rustc | apt |
| Tools | GNU coreutils, sed, grep, findutils, procps, curl | Debian |
| Size | 2 vCPU, 2048 MB | `CPU_COUNT` and `MEMORY_MB` in the script |

The versions match `docker/Dockerfile`. `build_template.py` pins each one as a constant.
To change a version, edit the constant and build again. E2B points the name `barebones-agent` at the newest build.
E2B adds its own packages to every template, for example systemd, sudo, openssh-server, git, and jq.

## How the env uses the template

- The env creates one sandbox per run, with the timeout `max_seconds` + 120 seconds (`SANDBOX_GRACE_SECONDS` in `src/harness/python/env/cloud.py`).
- At start, it uploads the working folder to `/home/user/work`. Commands run there as the user `user`.
- The file tools and `bash` act on the sandbox copy. The host folder does not change while the agent works.
- At stop, the env downloads `/home/user/work` back over the host folder and kills the sandbox. `target`, `__pycache__`, `.pytest_cache`, and `node_modules` stay in the sandbox.
- The eval harness grades on the host, so the host needs the toolchain of the codebase too.

To look for sandboxes that stayed alive, open the E2B dashboard, or run this command from the repo root. It reads the key from `.env` and does not print it:

```
env $(grep E2B_API_KEY .env) uv run python -c "from e2b import Sandbox; print([s.sandbox_id for s in Sandbox.list().next_items()])"
```

## Cost

E2B bills the sandbox time: $0.000014 per vCPU-second and $0.0000045 per GiB-second (checked 2026-09-23).
A 2 vCPU, 2 GB sandbox costs about $0.000037 per second, or $0.13 per hour. One trial of 300 seconds costs at most about $0.01.
