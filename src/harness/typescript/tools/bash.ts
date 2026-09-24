// The bash tool: run one shell command.
//
// This is part of the tools seam (a behavior seam).
// The tool calls env, never the machine directly.

import { EnvError, type Env } from "../env/base.ts";
import { envError, text, type Arguments, type Messages } from "./registry.ts";

const TIMEOUT_SECONDS = 30;

// Run the command. Return stdout, then stderr, then the exit code line.
export async function bash(env: Env, messages: Messages, args: Arguments): Promise<string> {
  let stdout: string;
  let stderr: string;
  let code: number;
  try {
    ({ stdout, stderr, code } = await env.run(args.command as string, TIMEOUT_SECONDS));
  } catch (error) {
    if (error instanceof EnvError) return envError(messages, error);
    throw error;
  }
  return withNewline(stdout) + withNewline(stderr) + text(messages, "exit_code", { n: code });
}

// Return the part with one newline at the end. An empty part stays empty.
function withNewline(part: string): string {
  if (part === "" || part.endsWith("\n")) return part;
  return part + "\n";
}
