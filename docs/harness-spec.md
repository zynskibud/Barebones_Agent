# Harness spec (draft 1)

## 1. Purpose

This file is the contract at the process boundary between `src/evals` and every agent harness.
The Python, TypeScript, and Go harnesses must all follow it.
If two harnesses score differently, compare each harness to this file.
If you change this file, change every harness.

## 2. Command line

Every harness is one program. Every harness takes the same flags.

| Flag | Required | Meaning |
|---|---|---|
| `--config <path>` | yes | The config file. |
| `--workdir <folder>` | yes | The working folder. The agent works only in this folder. |
| `--mode chat\|task` | no | Default `chat`. The eval harness always uses `task`. |
| `--prompt-file <path>` | task mode | The file that holds the task prompt. |
| `--transcript <path>` | task mode | Where the harness writes `transcript.jsonl`. |
| `--result <path>` | task mode | Where the harness writes `result.json`. |

Exit codes:

- `0`: the agent stopped on its own (`end_turn`).
- `2`: a limit stopped the agent (`max_turns`, `max_seconds`, `malformed_tool_call`).
- `3`: infrastructure error (`infra_error`), for example Ollama is unreachable or the harness crashed.

In task mode, the harness reads no stdin. It prints one line to stdout, the final status line:

```
stop_reason=<reason> turns=<N> seconds=<S>
```

## 3. Configuration

The config file is YAML. `config/baseline.yaml` holds these keys:

| Key | Values | Meaning |
|---|---|---|
| `harness` | `py`, `ts`, `go` | Which harness runs. |
| `tools` | `files`, `bash`, `files-bash` | Which tool set the model gets. |
| `env` | `local`, `docker`, `cloud` | Where tools run. |
| `codebase` | `python`, `typescript`, `rust` | Which task suite. |
| `model` | `qwen3:8b` | The Ollama model tag. |
| `think` | `false`, `true` | The Ollama `think` flag. |
| `num_ctx` | integer or `null` | Context size. `null` = Ollama default. |
| `temperature` | number or `null` | `null` = model default. |
| `max_turns` | `40` | Turn limit. |
| `max_seconds` | `600` | Wall-clock limit. |

Configuration ID rule:

```
<harness>.<tools>.<env>.<codebase>.<model-id>.<think-id>
```

- `model-id` is the Ollama tag with `:` replaced by `-`. For example, `qwen3:8b` becomes `qwen3-8b`.
- `think-id` is `think` if `think` is true, and `no-think` if `think` is false.

Baseline: `py.files-bash.local.python.qwen3-8b.no-think`.

`build_agent` is the composition root. It is the only place that reads the choices. Other code gets its parts from `build_agent`.

## 4. The loop

A turn is one model call.

1. Set `messages = [system, user prompt]`. Set `turn = 0` and `malformed = 0`.
2. Call the model with `messages`.
3. If the call fails, stop with `infra_error`.
4. Append the assistant message to `messages`.
5. If the assistant message has no tool calls, stop with `end_turn`.
6. Run every tool call in order. Append one tool result message per call, in the same order.
7. Set `turn = turn + 1`.
8. If `malformed >= 3`, stop with `malformed_tool_call`.
9. If `turn >= max_turns`, stop with `max_turns`.
10. If the wall clock since the first model call is `>= max_seconds`, stop with `max_seconds`.
11. Go to step 2.

Stop reasons (exact strings): `end_turn`, `max_turns`, `max_seconds`, `malformed_tool_call`, `infra_error`.

A malformed tool call is a call to a tool that does not exist, or a call with arguments that fail the schema.
For a malformed call, the harness returns an error tool result, adds 1 to `malformed`, and continues.
If one trial has 3 malformed calls, the harness stops with `malformed_tool_call`.

## 5. Model request

The harness sends `POST /api/chat` to Ollama with this body:

| Field | Value |
|---|---|
| `model` | `model` from config. |
| `messages` | The message list. |
| `tools` | The tool definitions for the tool set. |
| `stream` | `false` |
| `think` | `think` from config. |
| `options.num_ctx` | Only if `num_ctx` is not null. |
| `options.temperature` | Only if `temperature` is not null. |

`result.json` records the values that the run used.
If `num_ctx` or `temperature` is null, the harness records the value that `ollama show` reports.

The harness does not send thinking content back in later messages.
To verify: check the Ollama docs for a case where Ollama requires the thinking content in later messages.

## 6. System prompt

Every harness and every configuration uses this text, byte for byte:

```
You work inside one folder. All paths are relative to that folder.
The user will ask you to change the code in the folder.
Use your tools to look at the files, make the change, and check it when you can.
Do not ask the user questions. Nobody will answer.
Make the smallest change that does what the user asked.
When the change is done, stop and reply with one short sentence that says what you changed.
```

The tool descriptions say which tools exist. The system prompt text must not name tools.

## 7. Tool definitions

The harness sends these definitions exactly. Descriptions and schemas are byte for byte.

```json
{"type":"function","function":{"name":"read_file","description":"Read a text file in the working folder and return its contents.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"File path, relative to the working folder."}},"required":["path"],"additionalProperties":false}}}
```

```json
{"type":"function","function":{"name":"list_files","description":"List the files and folders in a folder of the working folder. Returns one name per line. Folder names end with /.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Folder path, relative to the working folder. Default is \".\"."}},"required":[],"additionalProperties":false}}}
```

```json
{"type":"function","function":{"name":"edit_file","description":"Replace old_str with new_str in a file. old_str must match the file text exactly once. To create a new file, give an empty old_str and the full file text as new_str.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"File path, relative to the working folder."},"old_str":{"type":"string","description":"The exact text to replace. Empty to create a new file."},"new_str":{"type":"string","description":"The new text."}},"required":["path","old_str","new_str"],"additionalProperties":false}}}
```

```json
{"type":"function","function":{"name":"bash","description":"Run a shell command in the working folder. Returns stdout, stderr, and the exit code. The command stops after 30 seconds.","parameters":{"type":"object","properties":{"command":{"type":"string","description":"The shell command to run."}},"required":["command"],"additionalProperties":false}}}
```

Tool sets:

| Set | Tools |
|---|---|
| `files` | `read_file`, `list_files`, `edit_file` |
| `bash` | `bash` |
| `files-bash` | `read_file`, `list_files`, `edit_file`, `bash` |

The harness sends the tools in the order of this table.
If the model calls a tool that is not in the set, the harness treats the call as malformed.

`edit_file` rules:

- If `old_str` is empty and the file does not exist, create the file with `new_str`.
- If `old_str` is empty and the file exists, return `error: <path> already exists`.
- If `old_str` matches exactly once, replace it and return `ok: edited <path>`. For a new file, return `ok: created <path>`.

## 8. Tool results and errors

Tool results are plain text. The harness uses these error strings exactly:

```
error: <path> is outside the working folder
error: <path> not found
error: <path> is a directory
error: <path> already exists
error: old_str not found in <path>
error: old_str matches more than once in <path>
error: command timed out after 30 seconds
error: unknown tool <name>
error: invalid arguments for <name>: <detail>
```

`<path>` is the path as the model sent it. `<detail>` is free text.

Truncation: if a tool result is longer than 10,000 characters, the harness keeps the first 10,000 characters and adds this line:

```
[truncated: N characters omitted]
```

`bash` runs in the working folder with a 30-second timeout.
The result is stdout, then stderr, then this final line:

```
exit code: N
```

## 9. Limits

| Limit | Value | Config key |
|---|---|---|
| Turns | 40 | `max_turns` |
| Wall clock, from the first model call | 600 s | `max_seconds` |
| bash timeout | 30 s | none |
| Tool result length | 10,000 characters | none |

If a config key exists, the harness reads the value from the config.

## 10. Transcript format

`transcript.jsonl` has one JSON object per line, in order. The `type` values are exact.

```json
{"type":"config","config_id":"py.files-bash.local.python.qwen3-8b.no-think","config":{"harness":"py","tools":"files-bash","env":"local","codebase":"python","model":"qwen3:8b","think":false,"num_ctx":null,"temperature":null,"max_turns":40,"max_seconds":600}}
{"type":"system","content":"You work inside one folder. ..."}
{"type":"user","content":"Fix the bug in parse_date so that ..."}
{"type":"assistant","content":"","tool_calls":[{"id":"call_0_0","name":"read_file","arguments":{"path":"src/dates.py"}}]}
{"type":"tool_result","tool_call_id":"call_0_0","name":"read_file","content":"def parse_date(s):\n    ..."}
{"type":"end","stop_reason":"end_turn","turns":5,"seconds":42.7}
```

- `config` is always the first line. `end` is always the last line.
- `assistant` has `content`. It has `tool_calls` only if the model made tool calls. It has `thinking` only if Ollama returned thinking.
- If Ollama returns no tool call id, the harness sets the id to `call_<turn>_<index>`.

## 11. result.json

The harness writes these keys. It writes `passed` and `grader_output` as `null`. The eval harness fills them in after grading.

```json
{
  "config_id": "py.files-bash.local.python.qwen3-8b.no-think",
  "task": "01",
  "trial": 1,
  "stop_reason": "end_turn",
  "turns": 5,
  "seconds": 42.7,
  "prompt_tokens": 18342,
  "completion_tokens": 911,
  "model": "qwen3:8b",
  "model_digest": "sha256:...",
  "num_ctx": 4096,
  "temperature": 0.6,
  "think": false,
  "exit_code": 0,
  "tool_calls": 6,
  "malformed_tool_calls": 0,
  "passed": null,
  "grader_output": null
}
```

`prompt_tokens` and `completion_tokens` are the sums over all model calls in the trial.

## 12. Working folder rules

- Every file tool path goes through `safe_path`.
- `safe_path` resolves the path. It follows `..` and symlinks.
- If the resolved path is outside the working folder, the tool returns `error: <path> is outside the working folder`.
- `bash` cannot be limited by path on the laptop (`env: local`). A command can read or write any file that the user can.
- The harness must log every bash command in the transcript.
- The eval harness searches every transcript for `hidden_tests` and `solution`. If it finds either string, it flags the trial.

## 13. Checklist for a new harness

- [ ] The flags and defaults match section 2.
- [ ] The exit codes and the stdout status line match section 2.
- [ ] The configuration ID matches section 3 for every axis value.
- [ ] The loop and the stop reasons match section 4.
- [ ] The request body matches section 5, with no extra fields.
- [ ] The system prompt bytes match section 6.
- [ ] The tool JSON bytes and tool order match section 7.
- [ ] The error strings match section 8 exactly.
- [ ] Truncation and the bash result format match section 8.
- [ ] The transcript record types and fields match section 10.
- [ ] `result.json` has exactly the keys in section 11.
- [ ] The baseline configuration on task 01 gives the same result as the Python harness.

## 14. Open points

- Ollama thinking round-trip: does Ollama need the thinking content back in later messages?
- `list_files`: is it recursive, and does it hide dotfiles?
- `docker` and `cloud` envs: how do they receive the working folder, and does `safe_path` run on the host or inside?
- Tool call ids: does Ollama return them for `qwen3:8b`, and does the tool message need `tool_name`?
- Bash output order: interleave stdout and stderr, or stdout first?
