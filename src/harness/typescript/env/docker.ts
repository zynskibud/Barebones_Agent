// The docker env: bash runs inside a Docker container.
//
// This is part of the env seam (a behavior seam).
// Tools call this module and never touch the container directly.
//
// The container mounts the host working folder at /work. The container and
// the host see the same files, so the eval harness grades the host folder.
//
// - read, write, list: act on the host folder with the safePath check of
//   LocalEnv. bash sees the working folder as /work, so safePath first maps
//   a path that starts with /work to the working folder.
// - run: docker exec bash -c <command> in /work. GNU timeout in the container
//   kills the command and every process it started.
// - start, stop: the container lives while its docker run client holds stdin
//   open. If the harness dies, even by SIGKILL, the pipe closes, the container
//   stops, and --rm removes it.
//
// Build the image once, from the repo root: docker build -t barebones-task docker/

import { spawn, type ChildProcess } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import { setTimeout as sleep } from "node:timers/promises";

import { EnvError, TIMEOUT, type RunResult } from "./base.ts";
import { LocalEnv, collect, killGroup, waitForExit } from "./local.ts";

const IMAGE = "barebones-task";
const MOUNT = "/work";
// Resource limits for every container, so that runs are comparable.
const CPUS = "2";
const MEMORY = "2g";
// The longest wait for one docker command and for the container to start, in seconds.
const DOCKER_SECONDS = 30;
const POLL_SECONDS = 0.1;
// How long the host waits for docker exec after the command timeout, in seconds.
const EXEC_GRACE_SECONDS = 10;
// timeout --signal KILL kills its whole process group, itself included,
// so docker exec exits with 128 + 9 when the command runs past the timeout.
const KILLED = 137;

// The result of one docker command.
type DockerResult = { code: number; stdout: string; stderr: string };

// Files on the host folder, commands in a container that mounts it.
export class DockerEnv extends LocalEnv {
  image: string;
  name: string;
  // The docker run client. The container lives while its stdin is open.
  keeper: ChildProcess | null;
  // Resolves when the client has exited and closed its pipes.
  keeperClosed: Promise<void>;
  keeperErrors: Buffer[];

  constructor(workdir: string, maxSeconds: number | null = null, image: string = IMAGE) {
    super(workdir, maxSeconds);
    this.image = image;
    this.name = `barebones-${crypto.randomBytes(6).toString("hex")}`;
    this.keeper = null;
    this.keeperClosed = Promise.resolve();
    this.keeperErrors = [];
  }

  // Map /work to the working folder, then run the LocalEnv check.
  safePath(path: string): string {
    if (path === MOUNT || path.startsWith(MOUNT + "/")) {
      path = "." + path.slice(MOUNT.length);
    }
    return super.safePath(path);
  }

  async start(): Promise<void> {
    const found = await docker("image", "inspect", "--format", "{{.Id}}", this.image);
    if (found.code !== 0) {
      if (found.stderr.includes("No such image")) {
        throw new Error(
          `the docker image ${this.image} does not exist. ` +
            `Build it from the repo root: docker build -t ${this.image} docker/`,
        );
      }
      throw new Error(`docker failed: ${lastLine(found.stderr)}`);
    }
    // detached gives the client its own session, as start_new_session does in Python.
    const keeper = spawn(
      "docker",
      [
        "run", "--rm", "--interactive", "--init", "--pull", "never",
        "--name", this.name,
        "--cpus", CPUS, "--memory", MEMORY,
        "--volume", `${this.root}:${MOUNT}`, "--workdir", MOUNT,
        this.image, "cat",
      ],
      { stdio: ["pipe", "ignore", "pipe"], detached: true },
    );
    this.keeperErrors = [];
    keeper.stderr?.on("data", (chunk: Buffer) => this.keeperErrors.push(chunk));
    // A client that has exited closes the pipe. Closing stdin then gives EPIPE, which is expected.
    keeper.stdin?.on("error", () => {});
    this.keeperClosed = new Promise((resolve) => {
      keeper.once("close", () => resolve());
      keeper.once("error", (error) => {
        this.keeperErrors.push(Buffer.from(String(error)));
        resolve();
      });
    });
    this.keeper = keeper;
    await this.waitUntilRunning(keeper);
  }

  // Return when the container runs. Remove it and throw if it does not start.
  async waitUntilRunning(keeper: ChildProcess): Promise<void> {
    const deadline = performance.now() + DOCKER_SECONDS * 1000;
    while (performance.now() < deadline) {
      if (hasExited(keeper)) {
        await this.keeperClosed;
        const error = Buffer.concat(this.keeperErrors).toString("utf8");
        await this.stop();
        throw new Error(`the container did not start: ${lastLine(error)}`);
      }
      const state = await docker("inspect", "--format", "{{.State.Running}}", this.name);
      if (state.stdout.trim() === "true") return;
      await sleep(POLL_SECONDS * 1000);
    }
    await this.stop();
    throw new Error(`the container did not start within ${DOCKER_SECONDS} seconds`);
  }

  // Remove the container. A second call does nothing.
  async stop(): Promise<void> {
    const keeper = this.keeper;
    this.keeper = null;
    if (keeper === null) return;
    const removed = await docker("rm", "--force", this.name);
    if (removed.code !== 0 && !removed.stderr.includes("No such container")) {
      fs.writeSync(2, `could not remove the container ${this.name}: ${lastLine(removed.stderr)}\n`);
    }
    // Close stdin and wait for the client, as Python's communicate() does.
    keeper.stdin?.end();
    const timer = new AbortController();
    const waited = await Promise.race([
      this.keeperClosed.then(() => true),
      sleep(DOCKER_SECONDS * 1000, false, { signal: timer.signal }).catch(() => false),
    ]);
    timer.abort();
    if (!waited) {
      killGroup(keeper);
      await waitForExit(keeper);
    }
  }

  async run(command: string, timeout: number): Promise<RunResult> {
    if (this.keeper === null || hasExited(this.keeper)) {
      throw new Error(`the container ${this.name} is not running`);
    }
    const child = spawn(
      "docker",
      ["exec", this.name, "timeout", "--signal", "KILL", String(timeout), "bash", "-c", command],
      { stdio: ["ignore", "pipe", "pipe"], detached: true },
    );
    const started = performance.now();
    const finished = await collect(child, timeout + EXEC_GRACE_SECONDS);
    if (finished.timedOut) throw new EnvError(TIMEOUT, command);
    if (finished.code === KILLED && performance.now() - started >= timeout * 1000) {
      throw new EnvError(TIMEOUT, command);
    }
    return { stdout: finished.stdout, stderr: finished.stderr, code: finished.code };
  }
}

// Run one docker command. Return the result. Never throw.
function docker(...args: string[]): Promise<DockerResult> {
  return new Promise((resolve) => {
    const child = spawn("docker", args, { stdio: ["ignore", "pipe", "pipe"] });
    const out: Buffer[] = [];
    const err: Buffer[] = [];
    child.stdout?.on("data", (chunk: Buffer) => out.push(chunk));
    child.stderr?.on("data", (chunk: Buffer) => err.push(chunk));
    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      resolve({ code: 1, stdout: "", stderr: `docker ${args[0]} did not answer in ${DOCKER_SECONDS} seconds` });
    }, DOCKER_SECONDS * 1000);
    child.on("error", (error: NodeJS.ErrnoException) => {
      clearTimeout(timer);
      const stderr = error.code === "ENOENT" ? "the docker command is not on PATH" : String(error);
      resolve({ code: 127, stdout: "", stderr });
    });
    child.on("close", (code: number | null) => {
      clearTimeout(timer);
      resolve({
        code: code ?? 1,
        stdout: Buffer.concat(out).toString("utf8"),
        stderr: Buffer.concat(err).toString("utf8"),
      });
    });
  });
}

// True when the process has exited or could not start.
function hasExited(child: ChildProcess): boolean {
  return child.exitCode !== null || child.signalCode !== null || child.pid === undefined;
}

// Return the last line of a docker error, or a note when there is none.
function lastLine(text: string): string {
  const lines = text.trim().split(/\r?\n/);
  return lines.length > 0 && lines[lines.length - 1] !== "" ? lines[lines.length - 1] : "no error text";
}
