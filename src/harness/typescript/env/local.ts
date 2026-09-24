// The local env: runs on the laptop.
//
// This is part of the env seam (a behavior seam). Every path goes through
// a safePath check that keeps the agent inside one working folder.
// Tools call this module and never touch the disk directly.

import { spawn, type ChildProcess } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import nodePath from "node:path";

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
  posixSplit,
  type RunResult,
} from "./base.ts";

// Files and commands on this machine, inside one working folder.
export class LocalEnv extends Env {
  root: string;

  constructor(workdir: string, maxSeconds: number | null = null) {
    super(workdir, maxSeconds);
    this.root = realPath(workdir);
    if (kindOf(this.root) !== "dir") {
      throw new Error(`the working folder ${workdir} does not exist`);
    }
  }

  // Resolve a path inside the working folder. Throw OUTSIDE_FOLDER if it leaves.
  safePath(path: string): string {
    const target = realPath(posixJoin(this.root, path));
    if (!isInside(target, this.root)) throw new EnvError(OUTSIDE_FOLDER, path);
    return target;
  }

  // Return the first prefix of path that is a file, spelled as the model sent it.
  // For `a.py/x` that is `a.py`. Return the whole path if no prefix is a file.
  filePrefix(path: string): string {
    const parts = path.split("/");
    for (let count = 1; count < parts.length; count++) {
      const prefix = parts.slice(0, count).join("/");
      if (prefix === "") continue;
      let candidate: string;
      try {
        candidate = this.safePath(prefix);
      } catch (error) {
        if (error instanceof EnvError && error.key === OUTSIDE_FOLDER) continue;
        throw error;
      }
      const kind = kindOf(candidate);
      if (kind !== null && kind !== "dir") return prefix;
    }
    return path;
  }

  async read(path: string): Promise<string> {
    const target = this.safePath(path);
    const kind = kindOf(target);
    if (kind === "dir") throw new EnvError(IS_DIRECTORY, path);
    if (kind !== "file") throw new EnvError(NOT_FOUND, path);
    return pythonText(fs.readFileSync(target));
  }

  async write(path: string, text: string): Promise<void> {
    const target = this.safePath(path);
    try {
      fs.mkdirSync(nodePath.dirname(target), { recursive: true });
      fs.writeFileSync(target, text, "utf8");
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code;
      if (code === "EEXIST" || code === "ENOTDIR") {
        // A parent of the path is a file, for example a.py in a.py/x.
        throw new EnvError(NOT_DIRECTORY, path, this.filePrefix(path));
      }
      throw error;
    }
  }

  async list(path: string): Promise<string[]> {
    const target = this.safePath(path);
    const kind = kindOf(target);
    if (kind === null) throw new EnvError(NOT_FOUND, path);
    if (kind !== "dir") throw new EnvError(NOT_DIRECTORY, path);
    const names = fs.readdirSync(target).sort(byCodePoint);
    return names.map((name) => (kindOf(nodePath.join(target, name)) === "dir" ? name + "/" : name));
  }

  async run(command: string, timeout: number): Promise<RunResult> {
    // detached gives bash its own session and process group, so that a
    // timeout can kill the command and every process it started.
    // stdin is inherited, as the Python harness does.
    const child = spawn("bash", ["-c", command], {
      cwd: this.root,
      stdio: ["inherit", "pipe", "pipe"],
      detached: true,
    });
    const finished = await collect(child, timeout);
    if (finished.timedOut) throw new EnvError(TIMEOUT, command);
    return { stdout: finished.stdout, stderr: finished.stderr, code: finished.code };
  }
}

// What collect() saw of one child process.
export type Finished = { stdout: string; stderr: string; code: number; timedOut: boolean };

// Wait for the child to exit and close its output, as Python's communicate() does.
// After timeout seconds, kill its process group and report timedOut.
export function collect(child: ChildProcess, timeout: number): Promise<Finished> {
  return new Promise((resolve, reject) => {
    const out: Buffer[] = [];
    const err: Buffer[] = [];
    let timedOut = false;
    child.stdout?.on("data", (chunk: Buffer) => out.push(chunk));
    child.stderr?.on("data", (chunk: Buffer) => err.push(chunk));
    const finish = (code: number | null, signal: NodeJS.Signals | null): void => {
      clearTimeout(timer);
      if (timedOut) {
        resolve({ stdout: "", stderr: "", code: -1, timedOut: true });
        return;
      }
      resolve({
        stdout: pythonText(Buffer.concat(out)),
        stderr: pythonText(Buffer.concat(err)),
        code: exitCode(code, signal),
        timedOut: false,
      });
    };
    const timer = setTimeout(() => {
      timedOut = true;
      killGroup(child);
      // A process that left the group can hold the pipes open, so wait for
      // the exit only and then drop the pipes.
      waitForExit(child).then(() => {
        child.stdout?.destroy();
        child.stderr?.destroy();
        finish(null, null);
      });
    }, timeout * 1000);
    child.on("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.on("close", finish);
  });
}

// Kill the process and every process in its group.
export function killGroup(child: ChildProcess): void {
  if (child.pid === undefined) return;
  try {
    process.kill(-child.pid, "SIGKILL");
  } catch {
    // The group has ended already.
  }
}

// Resolve when the process has exited.
export function waitForExit(child: ChildProcess): Promise<void> {
  if (child.exitCode !== null || child.signalCode !== null) return Promise.resolve();
  return new Promise((resolve) => child.once("exit", () => resolve()));
}

// The exit code as Python reports it: minus the signal number for a killed process.
export function exitCode(code: number | null, signal: NodeJS.Signals | null): number {
  if (code !== null) return code;
  if (signal !== null) return -(os.constants.signals[signal] ?? 1);
  return -1;
}

// Decode bytes as UTF-8 with Python's text mode rules: invalid bytes become
// U+FFFD, and \r\n and \r become \n (universal newlines).
export function pythonText(data: Buffer): string {
  return data.toString("utf8").replace(/\r\n?/g, "\n");
}

// Sort names by code point, as Python sorts strings.
export function byCodePoint(a: string, b: string): number {
  return Buffer.compare(Buffer.from(a, "utf8"), Buffer.from(b, "utf8"));
}

// Return "dir", "file", "other", or null when the path does not exist.
// Follows symlinks. Any error counts as "does not exist", as in Python.
export function kindOf(path: string): "dir" | "file" | "other" | null {
  try {
    const stat = fs.statSync(path);
    if (stat.isDirectory()) return "dir";
    if (stat.isFile()) return "file";
    return "other";
  } catch {
    return null;
  }
}

// True if target is the folder or a path below it.
export function isInside(target: string, folder: string): boolean {
  const prefix = folder.endsWith("/") ? folder : folder + "/";
  return target === folder || target.startsWith(prefix);
}

// Resolve symlinks and .. like Python's os.path.realpath(strict=False).
// A part that does not exist stays as it is, and the rest is still resolved.
export function realPath(path: string): string {
  const absolute = path.startsWith("/") ? path : posixJoin(process.cwd(), path);
  const [resolved] = joinRealPath("", absolute, new Map());
  return normPath(resolved);
}

// A port of posixpath._joinrealpath. seen maps each symlink to its resolved
// path, or to null while it is being resolved (a loop).
function joinRealPath(start: string, rest: string, seen: Map<string, string | null>): [string, boolean] {
  let path = start;
  if (rest.startsWith("/")) {
    rest = rest.slice(1);
    path = "/";
  }
  const names = rest.split("/");
  for (let index = 0; index < names.length; index++) {
    const name = names[index];
    if (name === "" || name === ".") continue;
    if (name === "..") {
      if (path !== "") {
        const [head, tail] = posixSplit(path);
        path = tail === ".." ? posixJoin(posixJoin(head, ".."), "..") : head;
      } else {
        path = "..";
      }
      continue;
    }
    const next = posixJoin(path, name);
    if (!isSymlink(next)) {
      path = next;
      continue;
    }
    const remaining = names.slice(index + 1).join("/");
    if (seen.has(next)) {
      const cached = seen.get(next);
      if (cached !== null && cached !== undefined) {
        path = cached;
        continue;
      }
      // A symlink loop: return the part so far and the rest unchanged.
      return [posixJoin(next, remaining), false];
    }
    seen.set(next, null);
    const [resolved, ok] = joinRealPath(path, fs.readlinkSync(next), seen);
    if (!ok) return [posixJoin(resolved, remaining), false];
    path = resolved;
    seen.set(next, resolved);
  }
  return [path, true];
}

function isSymlink(path: string): boolean {
  try {
    return fs.lstatSync(path).isSymbolicLink();
  } catch {
    return false;
  }
}
