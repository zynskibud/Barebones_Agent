// The file tools: read_file, list_files, edit_file.
//
// This is part of the tools seam (a behavior seam).
// Each tool calls env, never the machine directly.

import { EnvError, NOT_FOUND, isEnvError, type Env } from "../env/base.ts";
import { envError, text, type Arguments, type Messages } from "./registry.ts";

// Return the text of one file.
export async function readFile(env: Env, messages: Messages, args: Arguments): Promise<string> {
  const path = args.path as string;
  try {
    return await env.read(path);
  } catch (error) {
    if (error instanceof EnvError) return envError(messages, error, path);
    throw error;
  }
}

// Return the names in one folder, one per line. Not recursive. Dotfiles are hidden.
export async function listFiles(env: Env, messages: Messages, args: Arguments): Promise<string> {
  const path = Object.hasOwn(args, "path") ? (args.path as string) : ".";
  let names: string[];
  try {
    names = await env.list(path);
  } catch (error) {
    if (error instanceof EnvError) return envError(messages, error, path);
    throw error;
  }
  return names.filter((name) => !name.startsWith(".")).join("\n");
}

// Replace old_str once in a file, or create the file when old_str is empty.
export async function editFile(env: Env, messages: Messages, args: Arguments): Promise<string> {
  const path = args.path as string;
  const oldText = args.old_str as string;
  const newText = args.new_str as string;
  try {
    if (oldText === "") return await createFile(env, messages, path, newText);
    const current = await env.read(path);
    const count = current.split(oldText).length - 1;
    if (count === 0) return text(messages, "errors.old_str_not_found", { path });
    if (count > 1) return text(messages, "errors.old_str_multiple", { path });
    const index = current.indexOf(oldText);
    await env.write(path, current.slice(0, index) + newText + current.slice(index + oldText.length));
  } catch (error) {
    if (error instanceof EnvError) return envError(messages, error, path);
    throw error;
  }
  return text(messages, "ok.edited", { path });
}

// Create a file that does not exist yet.
async function createFile(env: Env, messages: Messages, path: string, content: string): Promise<string> {
  try {
    await env.read(path);
  } catch (error) {
    if (!isEnvError(error, NOT_FOUND)) throw error;
    await env.write(path, content);
    return text(messages, "ok.created", { path });
  }
  return text(messages, "errors.already_exists", { path });
}
