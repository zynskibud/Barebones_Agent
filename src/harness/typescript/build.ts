// The composition root.
//
// buildAgent(config) is the only place that reads the choices
// and builds the parts: model, tools, env, and loop.

import fs from "node:fs";
import nodePath from "node:path";
import { fileURLToPath } from "node:url";

import type { Env } from "./env/base.ts";
import { CloudEnv } from "./env/cloud.ts";
import { DockerEnv } from "./env/docker.ts";
import { LocalEnv } from "./env/local.ts";
import { makeModel, type Model } from "./model.ts";
import { bash } from "./tools/bash.ts";
import { editFile, listFiles, readFile } from "./tools/files.ts";
import { makeTools, type Definition, type Handler, type Messages, type Tools } from "./tools/registry.ts";

// This file is src/harness/typescript/build.ts, so the repo root is three folders up.
export const REPO_ROOT = nodePath.resolve(fileURLToPath(new URL("../../../", import.meta.url)));
const CONFIG_DIR = nodePath.join(REPO_ROOT, "config");
// The system prompt file when the config has no prompt key, relative to the repo root.
const DEFAULT_PROMPT = "config/system_prompt.txt";

// A value in the flat config file.
export type Value = string | number | boolean | null;
export type Config = { [key: string]: Value };

type EnvClass = new (workdir: string, maxSeconds: number | null) => Env;

const ENVS = new Map<string, EnvClass>([
  ["local", LocalEnv],
  ["docker", DockerEnv],
  ["cloud", CloudEnv],
]);

const HANDLERS = new Map<string, Handler>([
  ["read_file", readFile],
  ["list_files", listFiles],
  ["edit_file", editFile],
  ["bash", bash],
]);

// The built parts that the loop and main need.
export type Agent = {
  model: Model;
  tools: Tools;
  env: Env;
  systemPrompt: string;
  maxTurns: number;
  maxSeconds: number;
};

// Read the choices in config and build every part.
export function buildAgent(config: Config, workdir: string): Agent {
  const envClass = ENVS.get(String(config.env));
  if (envClass === undefined) throw new Error(`unknown env: ${config.env}`);
  // Every env gets max_seconds. An env that needs no time limit ignores it.
  const env = new envClass(workdir, config.max_seconds as number);
  const messages = JSON.parse(readText(nodePath.join(CONFIG_DIR, "messages.json"))) as Messages;
  const toolsFile = JSON.parse(readText(nodePath.join(CONFIG_DIR, "tools.json"))) as {
    tools: { [name: string]: Definition };
    sets: { [name: string]: string[] };
  };
  const names = Object.hasOwn(toolsFile.sets, String(config.tools)) ? toolsFile.sets[String(config.tools)] : undefined;
  if (names === undefined) throw new Error(`unknown tool set: ${config.tools}`);
  const definitions = names.map((name) => {
    if (!Object.hasOwn(toolsFile.tools, name)) throw new Error(`tools.json has no tool ${name}`);
    return toolsFile.tools[name];
  });
  const tools = makeTools(definitions, HANDLERS, env, messages);
  const model = makeModel(
    config.model as string,
    config.think,
    config.num_ctx as number | null,
    config.temperature as number | null,
    undefined,
    config.max_seconds as number,
  );
  const promptFile = config.prompt ?? DEFAULT_PROMPT;
  // resolve() keeps an absolute path as it is, as Python's / operator does.
  const systemPrompt = rstrip(readText(nodePath.resolve(REPO_ROOT, String(promptFile))));
  return {
    model,
    tools,
    env,
    systemPrompt,
    maxTurns: config.max_turns as number,
    maxSeconds: config.max_seconds as number,
  };
}

// Return <harness>.<tools>.<env>.<codebase>.<model-id>.<think-id>.
export function configId(config: Config): string {
  const modelId = String(config.model).replaceAll(":", "-");
  const thinkId = config.think ? "think" : "no-think";
  return [config.harness, config.tools, config.env, config.codebase, modelId, thinkId].join(".");
}

// Read a flat YAML config file: one `key: value` per line, with # comments.
export function loadConfig(path: string): Config {
  const config: Config = {};
  for (const rawLine of splitLines(readText(path))) {
    const line = strip(stripComment(rawLine));
    const colon = line.indexOf(":");
    if (line === "" || colon === -1) continue;
    config[strip(line.slice(0, colon))] = parseScalar(strip(line.slice(colon + 1)));
  }
  return config;
}

// Remove a # comment. A # inside quotes stays.
function stripComment(line: string): string {
  let quote: string | null = null;
  for (let index = 0; index < line.length; index++) {
    const char = line[index];
    if (quote !== null) {
      if (char === quote) quote = null;
    } else if (char === "'" || char === '"') {
      quote = char;
    } else if (char === "#" && (index === 0 || line[index - 1] === " " || line[index - 1] === "\t")) {
      return line.slice(0, index);
    }
  }
  return line;
}

// Turn one YAML scalar into a value, with the rules of the Python harness.
function parseScalar(raw: string): Value {
  if (raw === "" || raw === "null" || raw === "~") return null;
  if (raw === "true" || raw === "True") return true;
  if (raw === "false" || raw === "False") return false;
  if (raw.length >= 2 && raw[0] === raw[raw.length - 1] && (raw[0] === "'" || raw[0] === '"')) {
    return raw.slice(1, -1);
  }
  // Python's int() and float() allow one underscore between digits.
  if (/^[+-]?\d+(_\d+)*$/.test(raw)) return Number(raw.replaceAll("_", ""));
  if (/^[+-]?(\d+(_\d+)*(\.(\d+(_\d+)*)?)?|\.\d+(_\d+)*)([eE][+-]?\d+(_\d+)*)?$/.test(raw)) {
    return Number(raw.replaceAll("_", ""));
  }
  return raw;
}

// Read a text file the way Python's read_text does: UTF-8, and \r\n and \r
// become \n (universal newlines).
export function readText(path: string): string {
  return fs.readFileSync(path, "utf8").replace(/\r\n?/g, "\n");
}

// The characters that Python's str.strip() removes when it gets no argument.
const PY_SPACE = "\\t\\n\\v\\f\\r\\x1c-\\x1f \\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000";
const TRAILING_SPACE = new RegExp(`[${PY_SPACE}]+$`);
const LEADING_SPACE = new RegExp(`^[${PY_SPACE}]+`);

// Python's str.rstrip(). JavaScript's trimEnd() uses another set of characters.
export function rstrip(value: string): string {
  return value.replace(TRAILING_SPACE, "");
}

// Python's str.strip().
function strip(value: string): string {
  return rstrip(value).replace(LEADING_SPACE, "");
}

// Python's str.splitlines().
function splitLines(value: string): string[] {
  const lines = value.split(/\r\n|[\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029]/);
  if (lines.length > 0 && lines[lines.length - 1] === "") lines.pop();
  return lines;
}
