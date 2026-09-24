# The image for env: docker. One image holds the three task toolchains.
#
# Build it from the repo root:
#   docker build -t barebones-task docker/
#
# Every version is pinned. Each base is an official multi-arch Debian 13
# (trixie) image, so the same file builds on arm64 and amd64.

ARG PYTHON_IMAGE=python:3.12.14-slim-trixie
ARG NODE_IMAGE=node:24.21.0-trixie-slim
ARG RUST_IMAGE=rust:1.98.1-slim-trixie

FROM ${NODE_IMAGE} AS node
FROM ${RUST_IMAGE} AS rust

FROM ${PYTHON_IMAGE}

ARG PYTEST_VERSION=9.1.1

# rustc links through cc, so the image needs gcc and the C library headers.
# procps gives ps and kill, which the laptop also has.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libc6-dev procps \
    && rm -rf /var/lib/apt/lists/*

# Python: the base image has python and python3. Add pytest at the version
# that the eval harness uses on the host.
ENV PIP_ROOT_USER_ACTION=ignore
RUN pip install --no-cache-dir "pytest==${PYTEST_VERSION}"

# Node: the node binary and npm from the official image. Node 24 strips
# TypeScript types natively and runs .ts test files with node --test.
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# Rust: rustup and the stable toolchain (minimal profile: rustc, cargo, std)
# from the official image, at the same paths.
ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH
COPY --from=rust /usr/local/rustup /usr/local/rustup
COPY --from=rust /usr/local/cargo /usr/local/cargo

WORKDIR /work
CMD ["bash"]
