// Talk to the model through Ollama.
//
// This is the model seam (a value seam). The model is a tag string
// and a think flag, not a separate class per model.
//
// The requests use node:http and not fetch. Node's fetch stops a request
// when no response headers arrive in 300 seconds (UND_ERR_HEADERS_TIMEOUT),
// and there is no built-in way to change that. With stream false, Ollama
// sends the headers only when the reply is complete, so a long model call
// would end as infra_error and not as max_seconds.

import http from "node:http";

export const DEFAULT_URL = "http://localhost:11434";

// One chat message, as the harness builds it or as Ollama returned it.
export type Message = { [key: string]: unknown };

// A parsed JSON object from Ollama.
export type Body = { [key: string]: unknown };

// The result of one request. timeout is true when the call ran past its timeout.
export type Reply = { ok: true; body: Body } | { ok: false; timeout: boolean; error: string };

// One Ollama chat model: the tag, the think flag, and the options to send.
export type Model = {
  name: string;
  think: unknown;
  numCtx: number | null;
  temperature: number | null;
  url: string;
  // The HTTP timeout in seconds for the calls that give no timeout of their own.
  timeout: number;
};

export function makeModel(
  name: string,
  think: unknown,
  numCtx: number | null = null,
  temperature: number | null = null,
  url: string = DEFAULT_URL,
  timeout: number = 600,
): Model {
  return { name, think, numCtx, temperature, url: url.replace(/\/+$/, ""), timeout };
}

// POST /api/chat once. timeout is the HTTP timeout for this call, in seconds.
export async function chat(model: Model, messages: Message[], tools: unknown[], timeout: number): Promise<Reply> {
  const body: Body = {
    model: model.name,
    messages,
    tools,
    stream: false,
    think: model.think,
  };
  const options: Body = {};
  if (model.numCtx !== null) options.num_ctx = model.numCtx;
  if (model.temperature !== null) options.temperature = model.temperature;
  if (Object.keys(options).length > 0) body.options = options;
  const reply = await send("POST", model.url + "/api/chat", body, timeout);
  if (reply.ok && !("message" in reply.body)) {
    return { ok: false, timeout: false, error: `no message in the Ollama response: ${JSON.stringify(reply.body).slice(0, 500)}` };
  }
  return reply;
}

// Return the model digest from /api/tags, or null if the tag is not listed.
export async function digest(model: Model): Promise<string | null> {
  const body = need(await send("GET", model.url + "/api/tags", null, model.timeout));
  for (const entry of listOf(body.models)) {
    if (entry.name === model.name || entry.model === model.name) return (entry.digest as string) ?? null;
  }
  return null;
}

// Return the model's own parameters from /api/show, for example temperature.
export async function defaultParameters(model: Model): Promise<Map<string, string>> {
  const body = need(await send("POST", model.url + "/api/show", { model: model.name }, model.timeout));
  const parameters = new Map<string, string>();
  const raw = typeof body.parameters === "string" ? body.parameters : "";
  for (const line of raw.split(/\r\n|\n|\r/)) {
    const match = /^\s*(\S+)\s+(\S.*)$/s.exec(line);
    if (match) parameters.set(match[1], match[2].trim());
  }
  return parameters;
}

// Return the context length of the loaded model from /api/ps, or null if it is not loaded.
export async function loadedContextLength(model: Model): Promise<number | null> {
  const body = need(await send("GET", model.url + "/api/ps", null, model.timeout));
  for (const entry of listOf(body.models)) {
    if (entry.name === model.name || entry.model === model.name) return (entry.context_length as number) ?? null;
  }
  return null;
}

// The body of a good reply. Throw the error of a bad one.
function need(reply: Reply): Body {
  if (!reply.ok) throw new Error(reply.error);
  return reply.body;
}

function listOf(value: unknown): Body[] {
  return Array.isArray(value) ? (value as Body[]) : [];
}

// Send one request with a JSON body (or none) and parse the JSON reply.
// Turn every transport or format problem into a failed Reply. Never throw.
export function send(method: string, url: string, body: unknown, timeout: number): Promise<Reply> {
  return new Promise((resolve) => {
    const data = body === null ? null : Buffer.from(JSON.stringify(body), "utf8");
    const headers: { [key: string]: string | number } = {};
    if (data !== null) {
      headers["Content-Type"] = "application/json";
      headers["Content-Length"] = data.length;
    }
    let timedOut = false;
    // agent false: one connection per request, as urllib does.
    const request = http.request(url, { method, headers, agent: false }, (response) => {
      const chunks: Buffer[] = [];
      response.on("data", (chunk: Buffer) => chunks.push(chunk));
      response.on("error", (error) => finish(failure(error)));
      response.on("end", () => finish(parse(url, response.statusCode ?? 0, Buffer.concat(chunks))));
      response.on("close", () => {
        if (!response.complete) finish(failure(new Error("the connection closed before the reply was complete")));
      });
    });
    const timer = setTimeout(() => {
      timedOut = true;
      request.destroy(new Error("timeout"));
    }, timeout * 1000);
    const failure = (error: Error): Reply => {
      if (timedOut) return { ok: false, timeout: true, error: `no reply from ${url} in ${timeout.toFixed(1)} seconds` };
      return { ok: false, timeout: false, error: `cannot reach ${url}: ${error.message}` };
    };
    const finish = (reply: Reply): void => {
      clearTimeout(timer);
      resolve(reply);
    };
    request.on("error", (error) => finish(failure(error)));
    request.end(data ?? undefined);
  });
}

// Turn one HTTP reply into a Reply.
function parse(url: string, status: number, raw: Buffer): Reply {
  if (status < 200 || status >= 300) {
    return { ok: false, timeout: false, error: `HTTP ${status} from ${url}: ${raw.toString("utf8").slice(0, 500)}` };
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw.toString("utf8"));
  } catch {
    return { ok: false, timeout: false, error: `no JSON in the reply from ${url}` };
  }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    return { ok: false, timeout: false, error: `no JSON object in the reply from ${url}` };
  }
  if ("error" in parsed) return { ok: false, timeout: false, error: `Ollama error: ${String((parsed as Body).error)}` };
  return { ok: true, body: parsed as Body };
}
