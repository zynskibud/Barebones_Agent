// The agent loop.
//
// Send the messages to the model, run the tool calls it asks for,
// add the results, and repeat until the model stops or a limit is hit.

import { chat, type Message, type Model } from "./model.ts";
import type { Tools } from "./tools/registry.ts";

const MAX_MALFORMED = 3;
// The smallest HTTP timeout for one model call, in seconds.
const MIN_CALL_SECONDS = 1.0;

// One transcript record.
export type Entry = { [key: string]: unknown };

// Gets one transcript record per assistant message, tool result, and end.
export type RecordFn = (entry: Entry) => void;

// The facts of one run.
export type Run = {
  stopReason: string;
  turns: number;
  seconds: number;
  promptTokens: number;
  completionTokens: number;
  toolCalls: number;
  malformedToolCalls: number;
  error: string | null;
};

// One tool call as the loop runs it.
type Call = { id: string; name: string; args: unknown };

// Run the loop from the spec on messages, in place. Return the facts of the run.
export async function runLoop(
  model: Model,
  tools: Tools,
  messages: Message[],
  maxTurns: number,
  maxSeconds: number,
  record: RecordFn,
): Promise<Run> {
  let turn = 0;
  let malformed = 0;
  let toolCalls = 0;
  let promptTokens = 0;
  let completionTokens = 0;
  let error: string | null = null;
  let stopReason: string;
  const started = performance.now();
  const elapsed = (): number => (performance.now() - started) / 1000;
  while (true) {
    // Each call gets the time that remains, so the run ends near maxSeconds.
    const remaining = Math.max(maxSeconds - elapsed(), MIN_CALL_SECONDS);
    const reply = await chat(model, messages, tools.definitions, remaining);
    if (!reply.ok) {
      if (reply.timeout) {
        stopReason = "max_seconds";
      } else {
        error = reply.error;
        stopReason = "infra_error";
      }
      break;
    }
    turn += 1;
    promptTokens += (reply.body.prompt_eval_count as number) ?? 0;
    completionTokens += (reply.body.eval_count as number) ?? 0;
    const assistant = reply.body.message as Message;
    messages.push(assistant);
    const calls = readToolCalls(assistant, turn);
    record(assistantRecord(assistant, calls));
    if (calls.length === 0) {
      stopReason = "end_turn";
      break;
    }
    for (const call of calls) {
      const { content, malformed: bad } = await tools.call(call.name, call.args);
      toolCalls += 1;
      malformed += bad ? 1 : 0;
      messages.push({ role: "tool", tool_call_id: call.id, tool_name: call.name, content });
      record({ type: "tool_result", tool_call_id: call.id, name: call.name, content });
    }
    if (malformed >= MAX_MALFORMED) {
      stopReason = "malformed_tool_call";
      break;
    }
    if (turn >= maxTurns) {
      stopReason = "max_turns";
      break;
    }
    if (elapsed() >= maxSeconds) {
      stopReason = "max_seconds";
      break;
    }
  }
  const seconds = Number(elapsed().toFixed(1));
  const end: Entry = { type: "end", stop_reason: stopReason, turns: turn, seconds: oneDecimal(seconds) };
  if (error !== null) end.error = error;
  record(end);
  return {
    stopReason,
    turns: turn,
    seconds,
    promptTokens,
    completionTokens,
    toolCalls,
    malformedToolCalls: malformed,
    error,
  };
}

// Return the id, name, and arguments of each tool call. Fill in an id when Ollama gives none.
function readToolCalls(assistant: Message, turn: number): Call[] {
  const raw = Array.isArray(assistant.tool_calls) ? (assistant.tool_calls as Message[]) : [];
  return raw.map((call, index) => {
    const fn = (call.function || {}) as Message;
    const id = (call.id as string) || `call_${turn}_${index}`;
    const name = (fn.name as string) || "";
    let args: unknown = "arguments" in fn ? fn.arguments : {};
    if (typeof args === "string") args = parseJsonOrKeep(args);
    return { id, name, args };
  });
}

// Parse arguments that arrived as a JSON string. Keep the string if it is not JSON.
function parseJsonOrKeep(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

// Build the assistant transcript record.
function assistantRecord(assistant: Message, calls: Call[]): Entry {
  const entry: Entry = { type: "assistant", content: "content" in assistant ? assistant.content : "" };
  if (assistant.thinking) entry.thinking = assistant.thinking;
  if (calls.length > 0) {
    entry.tool_calls = calls.map((call) => ({ id: call.id, name: call.name, arguments: call.args }));
  }
  return entry;
}

declare global {
  interface JSON {
    rawJSON(text: string): unknown;
  }
}

// A number that JSON.stringify writes with one decimal, for example 42.0,
// as the Python harness writes a float. JSON.stringify(42) alone gives 42.
export function oneDecimal(value: number): unknown {
  return JSON.rawJSON(value.toFixed(1));
}
