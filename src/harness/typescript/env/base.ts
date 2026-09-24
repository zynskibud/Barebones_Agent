// The Env interface: what every environment offers the tools.
//
// An env is the place where the tools act: the laptop, a Docker container,
// or a cloud sandbox. The tools call the methods below and nothing else.
//
// Every env receives the host working folder path. The env is responsible
// for making that folder visible to itself, for example by mounting it.
//
// Paths are the strings that the model sent. The env resolves each path and
// keeps it inside the working folder. When a path or a command has a problem,
// the env throws an EnvError. Its key names the string in config/messages.json
// that the tool returns to the model.

// The keys in config/messages.json that an EnvError can name.
export const OUTSIDE_FOLDER = "errors.outside_folder";
export const NOT_FOUND = "errors.not_found";
export const IS_DIRECTORY = "errors.is_directory";
export const NOT_DIRECTORY = "errors.not_a_directory";
export const TIMEOUT = "errors.timeout";

// A problem that the tool reports to the model as text.
//
// path is the path to name in the message when it differs from the path that
// the model sent. For example, edit_file on `a.py/x` names the file `a.py`.
// When path is null, the tool names the path that the model sent.
export class EnvError extends Error {
  key: string;
  path: string | null;

  constructor(key: string, detail: string, path: string | null = null) {
    super(detail);
    this.name = "EnvError";
    this.key = key;
    this.path = path;
  }
}

export function isEnvError(error: unknown, key?: string): error is EnvError {
  return error instanceof EnvError && (key === undefined || error.key === key);
}

// What one shell command gave back.
export type RunResult = { stdout: string; stderr: string; code: number };

// The interface. Each env extends it and fills in every method.
//
// maxSeconds is the run's wall-clock limit from the config. An env that
// holds a remote resource (the cloud sandbox) sizes its own timeout from it.
// The other envs ignore it.
export class Env {
  workdir: string;
  maxSeconds: number | null;

  constructor(workdir: string, maxSeconds: number | null = null) {
    this.workdir = workdir;
    this.maxSeconds = maxSeconds;
  }

  // Set up the env. A no-op for envs that need no setup.
  async start(): Promise<void> {}

  // Tear down the env. A no-op for envs that need no teardown.
  async stop(): Promise<void> {}

  // Return the text of a file. Throw NOT_FOUND or IS_DIRECTORY.
  async read(_path: string): Promise<string> {
    throw new Error("read is not implemented");
  }

  // Write text to a file. Create the file and its parent folders if needed.
  async write(_path: string, _text: string): Promise<void> {
    throw new Error("write is not implemented");
  }

  // Return the sorted names in a folder. Folder names end with /.
  async list(_path: string): Promise<string[]> {
    throw new Error("list is not implemented");
  }

  // Run a shell command in the working folder.
  async run(_command: string, _timeout: number): Promise<RunResult> {
    throw new Error("run is not implemented");
  }
}

// Path helpers with the rules of Python's posixpath module. Node's path
// module differs in small cases: path.posix.join does not restart at an
// absolute part, and path.posix.normalize keeps a trailing slash.

// posixpath.join: an absolute part starts the path again.
export function posixJoin(base: string, part: string): string {
  if (part.startsWith("/")) return part;
  if (base === "" || base.endsWith("/")) return base + part;
  return base + "/" + part;
}

// posixpath.split: the head (without trailing slashes) and the last name.
export function posixSplit(path: string): [string, string] {
  const index = path.lastIndexOf("/") + 1;
  let head = path.slice(0, index);
  const tail = path.slice(index);
  if (head !== "" && head !== "/".repeat(head.length)) head = head.replace(/\/+$/, "");
  return [head, tail];
}

// posixpath.normpath: remove ".", "..", and double slashes as text.
export function normPath(path: string): string {
  if (path === "") return ".";
  let slashes = path.startsWith("/") ? 1 : 0;
  if (path.startsWith("//") && !path.startsWith("///")) slashes = 2;
  const parts: string[] = [];
  for (const part of path.split("/")) {
    if (part === "" || part === ".") continue;
    const keep = part !== ".." || (slashes === 0 && parts.length === 0) || (parts.length > 0 && parts[parts.length - 1] === "..");
    if (keep) parts.push(part);
    else if (parts.length > 0) parts.pop();
  }
  const joined = "/".repeat(slashes) + parts.join("/");
  return joined === "" ? "." : joined;
}
