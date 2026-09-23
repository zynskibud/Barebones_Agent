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

## 6. Shared data files

The exact strings live in data files, not in the code. Every harness loads these files at start. No harness copies their text into its code.

| File | Holds |
|---|---|
| `config/system_prompt.txt` | The system prompt. |
| `config/tools.json` | The four tool definitions, and the three tool sets. |
| `config/messages.json` | The error strings, the success strings, the truncation line, and the bash exit-code line. |

Rules:

- The harness uses the system prompt with trailing whitespace removed.
- The system prompt must not name tools. The tool definitions say which tools exist.
- Placeholders use braces, for example `{path}`. The harness replaces each placeholder with its value. `{path}` is the path as the model sent it. `{detail}` is free text. `{n}` is a number.
- If a string must change, change the data file. Do not change the code.

## 7. Tools

`config/tools.json` has two keys:

- `tools`: one definition for each tool, in the OpenAI tools format. The harness sends each definition exactly as stored.
- `sets`: the tools in each tool set, in order. The harness sends the tools in this order.

If the model calls a tool that is not in the set, the harness treats the call as malformed.

`edit_file` rules:

- If `old_str` is empty and the file does not exist, create the file with `new_str`. Return `ok.created`.
- If `old_str` is empty and the file exists, return `errors.already_exists`.
- If `old_str` matches exactly once, replace it. Return `ok.edited`.
- If `old_str` matches zero times, return `errors.old_str_not_found`.
- If `old_str` matches more than once, return `errors.old_str_multiple`.

## 8. Tool results

Tool results are plain text. Every error and success string comes from `config/messages.json`.

Truncation: if a tool result is longer than 10,000 characters, the harness keeps the first 10,000 characters. It then adds a new line with `truncated`, where `{n}` is the number of characters cut.

`bash` runs in the working folder with a 30-second timeout. The result is stdout, then stderr, then a final line with `exit_code`. If the command times out, the result is `errors.timeout`.

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
- If the resolved path is outside the working folder, the tool returns `errors.outside_folder`.
- `bash` cannot be limited by path on the laptop (`env: local`). A command can read or write any file that the user can.
- The harness must log every bash command in the transcript.
- The eval harness searches every transcript for `hidden_tests` and `solution`. If it finds either string, it flags the trial.

## 13. Checklist for a new harness

- [ ] The flags and defaults match section 2.
- [ ] The exit codes and the stdout status line match section 2.
- [ ] The configuration ID matches section 3 for every axis value.
- [ ] The loop and the stop reasons match section 4.
- [ ] The request body matches section 5, with no extra fields.
- [ ] The harness loads the three data files in section 6 and copies no text from them into its code.
- [ ] The tool order matches `sets` in `config/tools.json`.
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
