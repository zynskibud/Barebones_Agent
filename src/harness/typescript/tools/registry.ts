// The tool registry: definitions, argument checks, dispatch, and truncation.
//
// The tool definitions come from config/tools.json and go to the model
// exactly as stored. Every string that the model reads comes from
// config/messages.json. This module holds no tool text of its own.

import { EnvError, type Env } from "../env/base.ts";

export const MAX_RESULT_CHARS = 10_000;

// The parsed config/messages.json.
export type Messages = { [key: string]: unknown };

// One tool definition from config/tools.json, in the OpenAI tools format.
export type Definition = {
  type: string;
  function: { name: string; description?: string; parameters: Schema };
};

export type Schema = {
  type?: string;
  properties?: { [key: string]: { type?: string; description?: string } };
  required?: string[];
  additionalProperties?: boolean;
};

export type Arguments = { [key: string]: unknown };

export type Handler = (env: Env, messages: Messages, args: Arguments) => Promise<string>;

// The tool set for one run: the ordered definitions and the dispatch.
export type Tools = {
  definitions: Definition[];
  call: (name: string, args: unknown) => Promise<{ content: string; malformed: boolean }>;
};

// Return the string at a dotted key of messages.json with its placeholders filled.
// The placeholder rules are the rules of Python's str.format: {name} is a value,
// and {{ and }} are single braces.
export function text(messages: Messages, key: string, values: { [name: string]: string | number } = {}): string {
  let node: unknown = messages;
  for (const part of key.split(".")) node = (node as { [key: string]: unknown })[part];
  if (typeof node !== "string") throw new Error(`messages.json has no string at ${key}`);
  return node.replace(/\{\{|\}\}|\{(\w+)\}/g, (match: string, name: string | undefined) => {
    if (name === undefined) return match[0];
    if (!(name in values)) throw new Error(`messages.json ${key} needs a value for {${name}}`);
    return String(values[name]);
  });
}

// Turn an EnvError into the message string that its key names.
// The message names the path that the model sent, unless the env set error.path.
export function envError(messages: Messages, error: EnvError, path: string = ""): string {
  const named = error.path !== null ? error.path : path;
  return text(messages, error.key, { path: named });
}

// Return what is wrong with the arguments, or null when they fit the schema.
export function checkArguments(definition: Definition, args: unknown): string | null {
  const schema = definition.function.parameters;
  if (!isObject(args)) return "arguments are not a JSON object";
  const properties = schema.properties ?? {};
  for (const key of schema.required ?? []) {
    if (!Object.hasOwn(args, key)) return `missing required argument ${key}`;
  }
  for (const [key, value] of Object.entries(args)) {
    if (!Object.hasOwn(properties, key)) {
      if (schema.additionalProperties === false) return `unexpected argument ${key}`;
      continue;
    }
    const expected = properties[key].type;
    if (expected && !fitsType(value, expected)) return `${key} must be a ${expected}`;
  }
  return null;
}

// Check one JSON schema type. A bool never counts as an integer or a number.
export function fitsType(value: unknown, expected: string): boolean {
  if (expected === "string") return typeof value === "string";
  if (expected === "integer") return typeof value === "number" && Number.isInteger(value);
  if (expected === "number") return typeof value === "number";
  if (expected === "boolean") return typeof value === "boolean";
  if (expected === "object") return isObject(value);
  if (expected === "array") return Array.isArray(value);
  return true;
}

// Keep the first MAX_RESULT_CHARS characters and add the truncation line.
// A character is a code point, as in Python, not a UTF-16 code unit.
export function truncate(messages: Messages, result: string): string {
  // A string has at least as many code units as code points.
  if (result.length <= MAX_RESULT_CHARS) return result;
  let kept = 0;
  let end = 0;
  while (end < result.length && kept < MAX_RESULT_CHARS) {
    end += codePointWidth(result, end);
    kept += 1;
  }
  let cut = 0;
  for (let index = end; index < result.length; index += codePointWidth(result, index)) cut += 1;
  if (cut === 0) return result;
  return result.slice(0, end) + "\n" + text(messages, "truncated", { n: cut });
}

// 2 for a surrogate pair at index, else 1.
function codePointWidth(value: string, index: number): number {
  return (value.codePointAt(index) ?? 0) > 0xffff ? 2 : 1;
}

function isObject(value: unknown): value is Arguments {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

// Build the tool set for one run.
export function makeTools(
  definitions: Definition[],
  handlers: Map<string, Handler>,
  env: Env,
  messages: Messages,
): Tools {
  const byName = new Map<string, Definition>();
  for (const definition of definitions) byName.set(definition.function.name, definition);
  const chosen = new Map<string, Handler>();
  for (const name of byName.keys()) {
    const handler = handlers.get(name);
    if (handler === undefined) throw new Error(`no handler for the tool ${name}`);
    chosen.set(name, handler);
  }

  // Run one tool call. Return the result text and whether the call was malformed.
  async function call(name: string, args: unknown): Promise<{ content: string; malformed: boolean }> {
    const definition = byName.get(name);
    const handler = chosen.get(name);
    if (definition === undefined || handler === undefined) {
      return { content: text(messages, "errors.unknown_tool", { name }), malformed: true };
    }
    const problem = checkArguments(definition, args);
    if (problem !== null) {
      return { content: text(messages, "errors.invalid_arguments", { name, detail: problem }), malformed: true };
    }
    const result = await handler(env, messages, args as Arguments);
    return { content: truncate(messages, result), malformed: false };
  }

  return { definitions, call };
}
