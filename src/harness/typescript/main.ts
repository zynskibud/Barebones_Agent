// Start the agent.
//
// Chat mode: an interactive session in the terminal.
// Task mode: one task, then exit. The eval harness starts it as a separate program.
//
// Run it with Node 24 or later, which runs .ts files directly:
//   node src/harness/typescript/main.ts --config <file> --workdir <folder> [--mode task ...]
//
// All output goes through fs.writeSync, so that every line is out before the
// process exits. process.exit() at the end stops the process even when a
// library still holds a connection open.

import fs from "node:fs";
import nodePath from "node:path";
import readline from "node:readline";
import { parseArgs } from "node:util";

import { buildAgent, configId, loadConfig, readText, rstrip, type Agent, type Config } from "./build.ts";
import { oneDecimal, runLoop, type Entry, type RecordFn, type Run } from "./loop.ts";
import { defaultParameters, digest, loadedContextLength, type Message } from "./model.ts";

const EXIT_CODES = new Map<string, number>([
  ["end_turn", 0],
  ["max_turns", 2],
  ["max_seconds", 2],
  ["malformed_tool_call", 2],
  ["infra_error", 3],
]);

const RESULT_PREVIEW_CHARS = 300;

const PROGRAM = "main.ts";
const USAGE =
  `usage: ${PROGRAM} [-h] --config CONFIG --workdir WORKDIR [--mode {chat,task}]\n` +
  "               [--prompt-file PROMPT_FILE] [--transcript TRANSCRIPT] [--result RESULT]\n";
const HELP =
  USAGE +
  "\nBarebones Agent: one loop, a few tools, one local model.\n\n" +
  "options:\n" +
  "  -h, --help            show this help message and exit\n" +
  "  --config CONFIG       the config file\n" +
  "  --workdir WORKDIR     the working folder; the agent works only here\n" +
  "  --mode {chat,task}\n" +
  "  --prompt-file PROMPT_FILE\n" +
  "                        task mode: the file that holds the task prompt\n" +
  "  --transcript TRANSCRIPT\n" +
  "                        task mode: where to write transcript.jsonl\n" +
  "  --result RESULT       task mode: where to write result.json\n";

type Args = {
  config: string;
  workdir: string;
  mode: string;
  promptFile: string;
  transcript: string;
  result: string;
};

// The model settings that the run used, for result.json.
type Used = { modelDigest: string | null; numCtx: unknown; temperature: unknown };

async function main(argv: string[]): Promise<number> {
  const args = readArgs(argv);
  if (args.mode === "task") return runTask(args);
  return runChat(args);
}

// Parse the flags. A usage error exits with the infra_error code.
function readArgs(argv: string[]): Args {
  let values: { [name: string]: string | boolean | undefined };
  try {
    ({ values } = parseArgs({
      args: argv,
      options: {
        config: { type: "string" },
        workdir: { type: "string" },
        mode: { type: "string", default: "chat" },
        "prompt-file": { type: "string" },
        transcript: { type: "string" },
        result: { type: "string" },
        help: { type: "boolean", short: "h" },
      },
      strict: true,
      allowPositionals: false,
    }));
  } catch (error) {
    return usageError((error as Error).message);
  }
  if (values.help) {
    say(HELP);
    process.exit(0);
  }
  const missing = ["config", "workdir"].filter((name) => values[name] === undefined);
  if (missing.length > 0) {
    usageError(`the following arguments are required: ${missing.map((name) => "--" + name).join(", ")}`);
  }
  const mode = values.mode as string;
  if (mode !== "chat" && mode !== "task") {
    usageError(`argument --mode: invalid choice: '${mode}' (choose from 'chat', 'task')`);
  }
  if (mode === "task") {
    for (const flag of ["prompt-file", "transcript", "result"]) {
      if (values[flag] === undefined) usageError(`--${flag} is required in task mode`);
    }
  }
  return {
    config: values.config as string,
    workdir: values.workdir as string,
    mode,
    promptFile: (values["prompt-file"] as string) ?? "",
    transcript: (values.transcript as string) ?? "",
    result: (values.result as string) ?? "",
  };
}

function usageError(message: string): never {
  warn(USAGE + `${PROGRAM}: error: ${message}\n`);
  process.exit(EXIT_CODES.get("infra_error"));
}

// Run one task, write the transcript and the result, print the status line.
async function runTask(args: Args): Promise<number> {
  let config: Config;
  let transcript: number;
  try {
    config = loadConfig(args.config);
    transcript = openTranscript(args.transcript, config);
  } catch (error) {
    warn(`cannot start: ${errorSummary(error)}\n`);
    say("stop_reason=infra_error turns=0 seconds=0.0\n");
    return EXIT_CODES.get("infra_error") as number;
  }
  const record = makeWriter(transcript);
  let run: Run;
  let used: Used;
  let summary: string | null = null;
  try {
    const agent = buildAgent(config, args.workdir);
    const prompt = rstrip(readText(args.promptFile));
    record({ type: "system", content: agent.systemPrompt });
    record({ type: "user", content: prompt });
    const messages: Message[] = [
      { role: "system", content: agent.systemPrompt },
      { role: "user", content: prompt },
    ];
    // start() is inside the try, so a failed start still reaches stop().
    try {
      await agent.env.start();
      run = await runLoop(agent.model, agent.tools, messages, agent.maxTurns, agent.maxSeconds, record);
    } finally {
      await agent.env.stop();
    }
    used = await usedSettings(agent, config);
  } catch (error) {
    const detail = errorDetail(error);
    warn(detail + "\n");
    summary = errorSummary(error);
    run = crashRun(detail);
    record({ type: "end", stop_reason: "infra_error", turns: 0, seconds: oneDecimal(0), error: detail });
    used = { modelDigest: null, numCtx: config.num_ctx ?? null, temperature: config.temperature ?? null };
  }
  fs.closeSync(transcript);
  const exitCode = EXIT_CODES.get(run.stopReason) as number;
  writeResult(args.result, config, run, used, exitCode);
  if (run.error !== null) warn((summary ?? lastLine(run.error)) + "\n");
  say(`stop_reason=${run.stopReason} turns=${run.turns} seconds=${run.seconds.toFixed(1)}\n`);
  return exitCode;
}

// Open transcript.jsonl and write the config line. Return the file descriptor.
function openTranscript(path: string, config: Config): number {
  fs.mkdirSync(nodePath.dirname(path), { recursive: true });
  const handle = fs.openSync(path, "w");
  fs.writeSync(handle, JSON.stringify({ type: "config", config_id: configId(config), config }) + "\n");
  return handle;
}

// Return a record function that appends one JSON line per record, at once.
function makeWriter(handle: number): RecordFn {
  return (entry: Entry): void => {
    fs.writeSync(handle, JSON.stringify(entry) + "\n");
  };
}

// The run facts for a harness crash before or during the loop.
function crashRun(detail: string): Run {
  return {
    stopReason: "infra_error",
    turns: 0,
    seconds: 0,
    promptTokens: 0,
    completionTokens: 0,
    toolCalls: 0,
    malformedToolCalls: 0,
    error: detail,
  };
}

// Find the digest, context size, and temperature that the run used.
async function usedSettings(agent: Agent, config: Config): Promise<Used> {
  const used: Used = { modelDigest: null, numCtx: config.num_ctx ?? null, temperature: config.temperature ?? null };
  try {
    used.modelDigest = await digest(agent.model);
    if (used.numCtx === null) used.numCtx = await loadedContextLength(agent.model);
    if (used.temperature === null) {
      const raw = (await defaultParameters(agent.model)).get("temperature");
      used.temperature = raw !== undefined ? pythonFloat(raw) : null;
    }
  } catch (error) {
    warn(`could not read the model settings: ${errorSummary(error)}\n`);
  }
  return used;
}

// Read a number like Python's float() and keep it as a float in JSON:
// Python writes 1.0 where JSON.stringify would write 1.
function pythonFloat(raw: string): unknown {
  const value = Number(raw);
  if (raw.trim() === "" || Number.isNaN(value)) throw new Error(`could not convert string to float: '${raw}'`);
  if (Number.isInteger(value) && Math.abs(value) < 1e16) return JSON.rawJSON(value.toFixed(1));
  return value;
}

// Write result.json with exactly the keys in the spec.
function writeResult(path: string, config: Config, run: Run, used: Used, exitCode: number): void {
  // The names of the folders one and two levels above the file, as Python's
  // pathlib gives them: "." parts and empty parts do not count.
  const parts = path.split("/").filter((part) => part !== "" && part !== ".");
  const result = {
    config_id: configId(config),
    task: parts.length >= 3 ? parts[parts.length - 3] : "",
    trial: trialNumber(parts.length >= 2 ? parts[parts.length - 2] : ""),
    stop_reason: run.stopReason,
    turns: run.turns,
    seconds: oneDecimal(run.seconds),
    prompt_tokens: run.promptTokens,
    completion_tokens: run.completionTokens,
    model: config.model ?? null,
    model_digest: used.modelDigest,
    num_ctx: used.numCtx,
    temperature: used.temperature,
    think: config.think ?? null,
    exit_code: exitCode,
    tool_calls: run.toolCalls,
    malformed_tool_calls: run.malformedToolCalls,
    passed: null,
    grader_output: null,
  };
  fs.mkdirSync(nodePath.dirname(path), { recursive: true });
  fs.writeFileSync(path, JSON.stringify(result, null, 2) + "\n", "utf8");
}

// Read the trial number from the trial folder name, or null if it is not a number.
function trialNumber(name: string): number | null {
  return /^[0-9]+$/.test(name) ? Number(name) : null;
}

// Read user lines from stdin. Each line runs the loop on the shared history.
async function runChat(args: Args): Promise<number> {
  const config = loadConfig(args.config);
  const agent = buildAgent(config, args.workdir);
  const messages: Message[] = [{ role: "system", content: agent.systemPrompt }];
  say(`${configId(config)} in ${args.workdir}. Type exit to stop.\n`);
  const lines = readline.createInterface({ input: process.stdin, crlfDelay: Infinity })[Symbol.asyncIterator]();
  try {
    await agent.env.start();
    while (true) {
      say("> ");
      const next = await lines.next();
      if (next.done) break;
      const line = next.value as string;
      if (line.trim() === "exit") break;
      if (line.trim() === "") continue;
      messages.push({ role: "user", content: line });
      const run = await runLoop(agent.model, agent.tools, messages, agent.maxTurns, agent.maxSeconds, printRecord);
      if (run.stopReason === "infra_error") {
        warn(`${run.error}\n`);
        return EXIT_CODES.get("infra_error") as number;
      }
    }
  } finally {
    await agent.env.stop();
  }
  return 0;
}

// Show one transcript record to the person at the terminal.
function printRecord(entry: Entry): void {
  if (entry.type === "assistant") {
    if (entry.thinking) say(`[thinking: ${[...String(entry.thinking)].length} characters]\n`);
    if (entry.content) say(`${entry.content}\n`);
    const calls = (entry.tool_calls ?? []) as Array<{ name: string; arguments: unknown }>;
    for (const call of calls) say(`-> ${call.name} ${pythonDumps(call.arguments)}\n`);
  } else if (entry.type === "tool_result") {
    const characters = [...String(entry.content)];
    let preview = characters.join("");
    if (characters.length > RESULT_PREVIEW_CHARS) preview = characters.slice(0, RESULT_PREVIEW_CHARS).join("") + "...";
    say(`<- ${entry.name}: ${preview}\n`);
  } else if (entry.type === "end") {
    say(`[${entry.stop_reason}, ${entry.turns} turns, ${JSON.stringify(entry.seconds)} s]\n`);
  }
}

// JSON with the spacing of Python's json.dumps, for the chat display only.
function pythonDumps(value: unknown): string {
  if (Array.isArray(value)) return "[" + value.map(pythonDumps).join(", ") + "]";
  if (value !== null && typeof value === "object") {
    const pairs = Object.entries(value).map(([key, item]) => JSON.stringify(key) + ": " + pythonDumps(item));
    return "{" + pairs.join(", ") + "}";
  }
  return JSON.stringify(value) ?? "null";
}

// The full error text: the stack when there is one.
function errorDetail(error: unknown): string {
  if (error instanceof Error) return error.stack ?? `${error.name}: ${error.message}`;
  return String(error);
}

// One line that names the error.
function errorSummary(error: unknown): string {
  if (error instanceof Error) return `${error.name}: ${error.message}`;
  return String(error);
}

// The last line of a text.
function lastLine(text: string): string {
  const lines = rstrip(text).split("\n");
  return lines[lines.length - 1];
}

// Write to stdout at once.
function say(text: string): void {
  fs.writeSync(1, text);
}

// Write to stderr at once.
function warn(text: string): void {
  fs.writeSync(2, text);
}

// A stray promise failure inside a library must not end the run before
// result.json is written. Report it on stderr and go on.
process.on("unhandledRejection", (reason: unknown) => {
  warn(`unhandled promise failure: ${errorSummary(reason)}\n`);
});

main(process.argv.slice(2)).then(
  (code) => process.exit(code),
  (error: unknown) => {
    warn(errorDetail(error) + "\n");
    process.exit(1);
  },
);
