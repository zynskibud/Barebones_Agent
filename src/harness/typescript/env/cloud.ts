// The cloud env: runs in an E2B cloud sandbox (a Firecracker microVM).
//
// This is part of the env seam (a behavior seam).
// Tools call this module and never touch the sandbox directly.
//
// The harness and the model stay on this machine. Only the tools act in the sandbox.
// There is no shared folder, so the sandbox copy is the single source of truth
// while the agent works:
//
// - start() creates the sandbox and uploads the host working folder to WORK_ROOT.
// - read, write, list, and run act on the sandbox copy only.
// - stop() downloads WORK_ROOT back into the host working folder, so that the
//   eval harness can grade it on the host, and then kills the sandbox.
//
// safePath is pure path logic: it normalizes the path against WORK_ROOT and
// rejects any path that leaves it. It does not follow symlinks, because there is
// no host folder to resolve against. The sandbox is the boundary. The host is
// protected at stop(): the download is extracted with the rules of the Python
// tarfile data filter (env/tar.ts), so no member can land outside the host folder.
//
// The E2B SDK is imported inside start(). build.ts imports this module for
// every run, and the other envs must not load the SDK.
//
// The API key comes from E2B_API_KEY in the environment, or else from the
// E2B_API_KEY line in .env at the repo root. This module never prints it.

import fs from "node:fs";
import os from "node:os";
import nodePath from "node:path";
import { fileURLToPath } from "node:url";

import {
  Env,
  EnvError,
  IS_DIRECTORY,
  NOT_DIRECTORY,
  NOT_FOUND,
  OUTSIDE_FOLDER,
  TIMEOUT,
  normPath,
  posixJoin,
  type RunResult,
} from "./base.ts";
import { byCodePoint, kindOf, realPath } from "./local.ts";
import { extractSafely, packFolder, readArchive } from "./tar.ts";

type Sdk = typeof import("e2b");
type Sandbox = import("e2b").Sandbox;
type CommandHandle = import("e2b").CommandHandle;

const REPO_ROOT = nodePath.resolve(fileURLToPath(new URL("../../../../", import.meta.url)));
// The E2B template with the three task toolchains. cloud/README.md says how to build it.
const TEMPLATE = "barebones-agent";
const WORK_ROOT = "/home/user/work";
const UPLOAD_ARCHIVE = "/tmp/barebones-upload.tar.gz";
const DOWNLOAD_ARCHIVE = "/tmp/barebones-download.tar.gz";
// The sandbox timeout is max_seconds plus this grace. The eval harness kills a
// stuck harness at max_seconds + 60, so the sandbox outlives the harness. If the
// harness dies before stop(), E2B kills the sandbox at this timeout.
const SANDBOX_GRACE_SECONDS = 120;
// The max_seconds that a direct construction without one gets.
const DEFAULT_MAX_SECONDS = 600;
// The commands that the env runs for itself (upload, download, checks) get this timeout.
const SETUP_SECONDS = 120;
// Build output that stays in the sandbox. The download at stop() leaves it out.
const DOWNLOAD_EXCLUDES = ["target", "__pycache__", ".pytest_cache", "node_modules"];
const METADATA = { app: "barebones-agent" };

// Files and commands in one E2B sandbox, inside one working folder.
export class CloudEnv extends Env {
  hostRoot: string;
  sandboxSeconds: number;
  sdk: Sdk | null;
  sandbox: Sandbox | null;
  refreshed: number;

  constructor(workdir: string, maxSeconds: number | null = null) {
    super(workdir, maxSeconds);
    this.hostRoot = realPath(workdir);
    if (kindOf(this.hostRoot) !== "dir") {
      throw new Error(`the working folder ${workdir} does not exist`);
    }
    const limit = maxSeconds !== null ? maxSeconds : DEFAULT_MAX_SECONDS;
    this.sandboxSeconds = Math.trunc(limit + SANDBOX_GRACE_SECONDS);
    this.sdk = null;
    this.sandbox = null;
    this.refreshed = 0;
  }

  // Create the sandbox from the template and upload the working folder.
  async start(): Promise<void> {
    if (this.sandbox !== null) return;
    this.sdk = await loadSdk();
    this.sandbox = await this.sdk.Sandbox.create(TEMPLATE, {
      timeoutMs: this.sandboxSeconds * 1000,
      metadata: METADATA,
      apiKey: apiKey(),
    });
    this.refreshed = performance.now();
    try {
      await this.upload();
    } catch (error) {
      // A failed start must not leak the sandbox.
      await this.kill();
      throw error;
    }
  }

  // Download the working folder to the host, then kill the sandbox. Safe to call twice.
  async stop(): Promise<void> {
    if (this.sandbox === null) return;
    try {
      await this.download();
    } finally {
      await this.kill();
    }
  }

  // Return the sandbox path under WORK_ROOT. Throw OUTSIDE_FOLDER if it leaves.
  safePath(path: string): string {
    const target = normPath(posixJoin(WORK_ROOT, path));
    if (target !== WORK_ROOT && !target.startsWith(WORK_ROOT + "/")) {
      throw new EnvError(OUTSIDE_FOLDER, path);
    }
    return target;
  }

  async read(path: string): Promise<string> {
    const sdk = this.loaded();
    const target = this.safePath(path);
    await this.keepAlive();
    let data: Uint8Array;
    try {
      data = await this.box().files.read(target, { format: "bytes" });
    } catch (error) {
      if (error instanceof sdk.FileNotFoundError) throw new EnvError(NOT_FOUND, path);
      if (!(error instanceof sdk.SandboxError)) throw error;
      const kind = await this.kind(target);
      if (kind === "dir") throw new EnvError(IS_DIRECTORY, path);
      if (kind === null) throw new EnvError(NOT_FOUND, path);
      throw error;
    }
    return Buffer.from(data).toString("utf8");
  }

  async write(path: string, text: string): Promise<void> {
    const sdk = this.loaded();
    const target = this.safePath(path);
    await this.keepAlive();
    try {
      // The sandbox creates the parent folders.
      await this.box().files.write(target, text);
    } catch (error) {
      if (!(error instanceof sdk.SandboxError)) throw error;
      // A parent of the path is a file, for example a.py in a.py/x.
      const prefix = await this.filePrefix(path);
      if (prefix === null) throw error;
      throw new EnvError(NOT_DIRECTORY, path, prefix);
    }
  }

  // Return the first prefix of path that is a file, spelled as the model sent it.
  // For `a.py/x` that is `a.py`. Return null if no prefix is a file.
  async filePrefix(path: string): Promise<string | null> {
    const parts = path.split("/");
    for (let count = 1; count < parts.length; count++) {
      const prefix = parts.slice(0, count).join("/");
      if (prefix === "") continue;
      let target: string;
      try {
        target = this.safePath(prefix);
      } catch (error) {
        if (error instanceof EnvError && error.key === OUTSIDE_FOLDER) continue;
        throw error;
      }
      if ((await this.kind(target)) === "file") return prefix;
    }
    return null;
  }

  async list(path: string): Promise<string[]> {
    const sdk = this.loaded();
    const target = this.safePath(path);
    await this.keepAlive();
    let entries: Array<{ name: string; type?: string }>;
    try {
      entries = await this.box().files.list(target, { depth: 1 });
    } catch (error) {
      if (error instanceof sdk.FileNotFoundError) throw new EnvError(NOT_FOUND, path);
      if (!(error instanceof sdk.SandboxError)) throw error;
      const kind = await this.kind(target);
      if (kind === null) throw new EnvError(NOT_FOUND, path);
      if (kind !== "dir") throw new EnvError(NOT_DIRECTORY, path);
      throw error;
    }
    entries.sort((a, b) => byCodePoint(a.name, b.name));
    return entries.map((entry) => (entry.type === sdk.FileType.DIR ? entry.name + "/" : entry.name));
  }

  async run(command: string, timeout: number): Promise<RunResult> {
    const sdk = this.loaded();
    await this.keepAlive();
    // E2B runs every command as /bin/bash -l -c <cmd> in the process group
    // of its daemon. exec setsid gives bash -c its own process group, with
    // the group id equal to the handle pid, so that a timeout can kill the group.
    const wrapped = "exec setsid bash -c " + shellQuote(command);
    const handle: CommandHandle = await this.box().commands.run(wrapped, {
      background: true,
      cwd: WORK_ROOT,
      timeoutMs: timeout * 1000,
    });
    try {
      const result = await handle.wait();
      return { stdout: result.stdout, stderr: result.stderr, code: result.exitCode };
    } catch (error) {
      if (error instanceof sdk.CommandExitError) {
        return { stdout: error.stdout, stderr: error.stderr, code: error.exitCode };
      }
      if (error instanceof sdk.TimeoutError) {
        // The E2B timeout ends the stream only. The command keeps running.
        await this.killGroup(handle.pid);
        throw new EnvError(TIMEOUT, command);
      }
      throw error;
    }
  }

  // Copy every file under the host working folder to WORK_ROOT.
  async upload(): Promise<void> {
    const archive = packFolder(this.hostRoot);
    await this.box().files.write(UPLOAD_ARCHIVE, new Blob([archive]));
    await this.box().commands.run(
      `mkdir -p ${WORK_ROOT} && tar -xzf ${UPLOAD_ARCHIVE} -C ${WORK_ROOT} && rm ${UPLOAD_ARCHIVE}`,
      { timeoutMs: SETUP_SECONDS * 1000 },
    );
  }

  // Replace the host working folder contents with WORK_ROOT.
  //
  // Host files that the agent deleted in the sandbox are deleted on the host.
  // The host folder changes only after the whole archive is extracted.
  // Build output (DOWNLOAD_EXCLUDES) stays in the sandbox.
  async download(): Promise<void> {
    const excludes = DOWNLOAD_EXCLUDES.map((name) => `--exclude=${shellQuote(name)}`).join(" ");
    await this.box().commands.run(`tar -czf ${DOWNLOAD_ARCHIVE} -C ${WORK_ROOT} ${excludes} .`, {
      user: "root",
      timeoutMs: SETUP_SECONDS * 1000,
    });
    const data = await this.box().files.read(DOWNLOAD_ARCHIVE, { format: "bytes", user: "root" });
    const staging = fs.mkdtempSync(nodePath.join(os.tmpdir(), "barebones-download-"));
    try {
      extractSafely(readArchive(Buffer.from(data)), staging);
      for (const name of fs.readdirSync(this.hostRoot)) {
        fs.rmSync(nodePath.join(this.hostRoot, name), { recursive: true, force: true });
      }
      for (const name of fs.readdirSync(staging)) {
        move(nodePath.join(staging, name), nodePath.join(this.hostRoot, name));
      }
    } finally {
      fs.rmSync(staging, { recursive: true, force: true });
    }
  }

  // Return "dir", "file", or null when the sandbox path does not exist.
  //
  // Only the error paths call this. A shell test follows symlinks like the
  // local env, and it answers for every path (for example a path under a
  // file, where the E2B file API gives an internal error).
  async kind(target: string): Promise<"dir" | "file" | null> {
    const quoted = shellQuote(target);
    const result = await this.box().commands.run(
      `if [ -d ${quoted} ]; then echo dir; elif [ -e ${quoted} ]; then echo file; fi`,
      { timeoutMs: SETUP_SECONDS * 1000 },
    );
    const answer = result.stdout.trim();
    return answer === "dir" || answer === "file" ? answer : null;
  }

  // Kill the command and every process in its group.
  async killGroup(pid: number): Promise<void> {
    const sdk = this.loaded();
    try {
      await this.box().commands.run(`kill -9 -- -${pid}`, { timeoutMs: SETUP_SECONDS * 1000 });
    } catch (error) {
      // The group ended on its own.
      if (!(error instanceof sdk.CommandExitError)) throw error;
    }
  }

  // Push the sandbox timeout forward when half of it has passed (for long chats).
  async keepAlive(): Promise<void> {
    const now = performance.now();
    if (now - this.refreshed > (this.sandboxSeconds / 2) * 1000) {
      await this.box().setTimeout(this.sandboxSeconds * 1000);
      this.refreshed = now;
    }
  }

  // Kill the sandbox and forget it.
  //
  // A failed kill does not fail the run: the work is already on the host,
  // and E2B kills the sandbox at its timeout.
  async kill(): Promise<void> {
    const sandbox = this.sandbox;
    this.sandbox = null;
    if (sandbox === null) return;
    try {
      await sandbox.kill();
    } catch (error) {
      fs.writeSync(2, `cloud env: could not kill sandbox ${sandbox.sandboxId}: ${String(error)}\n`);
    }
  }

  // The SDK module. start() loads it.
  loaded(): Sdk {
    if (this.sdk === null) throw new Error("the cloud env is not started");
    return this.sdk;
  }

  // The sandbox. start() creates it.
  box(): Sandbox {
    if (this.sandbox === null) throw new Error("the cloud env has no sandbox");
    return this.sandbox;
  }
}

// Load the E2B SDK. It is the one npm package of this harness.
async function loadSdk(): Promise<Sdk> {
  try {
    return await import("e2b");
  } catch (error) {
    throw new Error(
      "cannot load the e2b package. Install it once, from the repo root: " +
        `npm install --prefix src/harness/typescript (${String(error)})`,
    );
  }
}

// Move a file, symlink, or folder tree. Copy when the two paths are on different disks.
function move(from: string, to: string): void {
  try {
    fs.renameSync(from, to);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "EXDEV") throw error;
    fs.cpSync(from, to, { recursive: true, verbatimSymlinks: true, preserveTimestamps: true });
    fs.rmSync(from, { recursive: true, force: true });
  }
}

// Quote one shell word like Python's shlex.quote.
function shellQuote(word: string): string {
  if (word === "") return "''";
  if (!/[^\w@%+=:,./-]/.test(word)) return word;
  return "'" + word.replaceAll("'", `'"'"'`) + "'";
}

// Return E2B_API_KEY from the environment, or else from .env at the repo root.
function apiKey(): string {
  const key = process.env.E2B_API_KEY;
  if (key) return key;
  const envFile = nodePath.join(REPO_ROOT, ".env");
  if (kindOf(envFile) === "file") {
    for (const line of fs.readFileSync(envFile, "utf8").split(/\r?\n/)) {
      const separator = line.indexOf("=");
      if (separator !== -1 && line.slice(0, separator).trim() === "E2B_API_KEY") {
        return line.slice(separator + 1).trim().replace(/^['"]+|['"]+$/g, "");
      }
    }
  }
  throw new Error("E2B_API_KEY is not set. Set it in the environment or in .env at the repo root.");
}
