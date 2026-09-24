# The docker env image

`env: docker` runs the `bash` tool in a container of the image `barebones-task`.
The harness does not build the image. Build it once, from the repo root:

```
docker build -t barebones-task docker/
```

If the image does not exist, the harness stops with `infra_error` and prints this command.

## What the image holds

| Part | Version | Source |
|---|---|---|
| Base | Debian 13 (trixie), slim | `python:3.12.14-slim-trixie` |
| Python | 3.12.14, with `python` and `python3` | the base image |
| pytest | 9.1.1, the eval harness version | pip |
| Node | 24.21.0, with npm | `node:24.21.0-trixie-slim` |
| Rust | 1.98.1 (rustc, cargo, rustup, minimal profile) | `rust:1.98.1-slim-trixie` |
| C linker | gcc and libc6-dev, for rustc | apt |
| Tools | GNU coreutils, sed, grep, findutils, procps | Debian |

Node 24 strips TypeScript types natively. `node --test` finds and runs `.ts` test files.

The `Dockerfile` pins each version as an `ARG`. To change a version, edit the `ARG` and build again.
The size is about 1.4 GB on disk and 350 MB compressed. The Rust toolchain uses about 510 MB and gcc about 190 MB.

## How the env uses the image

- The container mounts the host working folder at `/work`. The container and the host see the same files.
- The file tools run on the host. `bash` runs in the container, in `/work`, and cannot see other host files.
- Each container gets 2 CPUs and 2 GB of memory (`CPUS` and `MEMORY` in `src/harness/python/env/docker.py`).
- The container runs as root. On macOS, Docker Desktop gives the files that it writes to the host user.
- The container stops when the harness ends, also when the harness is killed. Each name starts with `barebones-`.

To look for containers that stayed alive, run this command:

```
docker ps -a --filter name=barebones-
```
