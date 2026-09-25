# Harness spec

Version 1. Frozen 2026-09-23. A change to this file after this date needs a new version number and a rerun of the baseline.

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

The harness uses the prompt file text with trailing whitespace removed.

Exit codes:

- `0`: the agent stopped on its own (`end_turn`).
- `2`: a limit stopped the agent (`max_turns`, `max_seconds`, `malformed_tool_call`).
- `3`: infrastructure error (`infra_error`), for example Ollama is unreachable, the env is not built, or the harness crashed.

In task mode, the harness reads no stdin. It prints one line to stdout, the final status line:

```
stop_reason=<reason> turns=<N> seconds=<S>
```

Everything else that the harness has to say goes to stderr.
The eval harness passes absolute paths for every flag. It waits `max_seconds` + 60 seconds, then kills the harness and its whole process group.
If the harness crashes, it still writes the transcript `end` line and `result.json`, with `infra_error` and exit code 3.

Chat mode reads one user line at a time from stdin. Each line runs the loop on the shared message history.
The harness prints the tool calls, a short form of each tool result, and the reply, so that a person can watch the agent work.
The line `exit` or the end of input stops it. Chat mode writes no transcript and no result.

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
| `max_turns` | `20` | Turn limit. |
| `max_seconds` | `300` | Wall-clock limit. |
| `prompt` | a path relative to the repo root | Optional, not in `config/baseline.yaml`. The system prompt file. If the key is absent or null, the harness reads `config/system_prompt.txt`. A different file is an experiment, not a v1 run. |

The config file is flat YAML: one `key: value` pair per line, with optional `#` comments.
A harness needs no YAML library to read it.

Configuration ID rule:

```
<harness>.<tools>.<env>.<codebase>.<model-id>.<think-id>
```

- `model-id` is the Ollama tag with `:` replaced by `-`. For example, `qwen3:8b` becomes `qwen3-8b`.
- `think-id` is `think` if `think` is true, and `no-think` if `think` is false.

Baseline: `py.files-bash.docker.python.qwen3-8b.no-think`. The pilot and Experiment 1 ran on `local`, before the baseline moved to `docker` on 2026-09-25 (section 15, item h).

`build_agent` is the composition root. It is the only place that reads the choices. Other code gets its parts from `build_agent`.

## 4. The loop

A turn is one model call.

1. Set `messages = [system, user prompt]`. Set `turn = 0` and `malformed = 0`.
2. Call the model with `messages`.
3. If the call runs past its timeout (section 5), stop with `max_seconds`. If the call fails in any other way, stop with `infra_error`.
4. Set `turn = turn + 1`. Append the assistant message to `messages`.
5. If the assistant message has no tool calls, stop with `end_turn`.
6. Run every tool call in order. Append one tool result message per call, in the same order.
7. If `malformed >= 3`, stop with `malformed_tool_call`.
8. If `turn >= max_turns`, stop with `max_turns`.
9. If the wall clock since the first model call is `>= max_seconds`, stop with `max_seconds`.
10. Go to step 2.

Stop reasons (exact strings): `end_turn`, `max_turns`, `max_seconds`, `malformed_tool_call`, `infra_error`.

`turns` is the number of model calls that returned. A run where the first reply has no tool calls has `turns` 1.
The wall clock starts right before the first model call and stops when the loop stops. `seconds` has one decimal.

A malformed tool call is one of these:

- a call to a tool that does not exist, or that is not in the tool set (`errors.unknown_tool`);
- a call with arguments that fail the schema (`errors.invalid_arguments`): the arguments are not a JSON object, a required key is missing, a key is not in `properties` while `additionalProperties` is false, or a value has the wrong JSON type.

For a malformed call, the harness returns the error string as the tool result, adds 1 to `malformed`, and continues.
The malformed call still gets a tool result message, so that the message list stays in call and result pairs.
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

The harness sends `think` on every call, also when it is `false`. The qwen3:8b template only appends `/no_think` when the field is present.
The HTTP timeout for one model call is the time that remains: `max_seconds` minus the seconds since the first model call, with a floor of 1 second.
A call that runs past its timeout stops the loop with `max_seconds`, not `infra_error`. That call did not return, so it does not count as a turn.
So one run ends close to `max_seconds`, and the eval harness kill at `max_seconds` + 60 catches only a stuck harness.

The messages have these shapes:

| Role | Shape |
|---|---|
| `system` | `{"role": "system", "content": "<system prompt>"}` |
| `user` | `{"role": "user", "content": "<prompt>"}` |
| `assistant` | The `message` object exactly as Ollama returned it, including `thinking` and `tool_calls`. |
| `tool` | `{"role": "tool", "tool_call_id": "<id>", "tool_name": "<name>", "content": "<result>"}` |

Thinking round trip: the harness sends the assistant message back exactly as Ollama returned it. That includes `thinking` when Ollama returned it.
Checked 2026-09-23 on Ollama 0.34.3 with qwen3:8b: Ollama accepts the history both with and without `thinking`, and the model finishes the task both ways.
The Ollama tool-calling docs say to return `thinking`, `content`, and `tool_calls` together with the tool results in the follow-up request.
The qwen3:8b chat template renders `<think>` for assistant messages that come after the last user message, which is the tool-calling chain of the current task.
The cost is prompt tokens: about 200 to 360 more per step in a three-step test.

Tool call ids: Ollama 0.34.3 returns an `id` on every tool call, for example `call_8xq7xg9p`. The harness uses that id.
If Ollama returns no id, the id is `call_<turn>_<index>`, with the turn number from section 4 and the 0-based index of the call in the message.
The tool message carries both `tool_call_id` and `tool_name`. Ollama accepts a tool message with both, one, or none of them.
The qwen3:8b template renders only the `content` of a tool message, so the model matches results to calls by order. That is why the harness appends the results in call order.

Known template fact: the qwen3:8b template renders either the content or the tool calls of an assistant message, not both.
If the model returns text and tool calls in one message, the model sees only the text in later turns. The harness does not change the message.

`result.json` records the values that the run used:

- `model_digest` is the `digest` that `GET /api/tags` lists for the model tag, as Ollama returns it.
- If `num_ctx` is null, the harness records `context_length` from `GET /api/ps` after the run. If the model is not loaded, it records null.
- If `temperature` is null, the harness records the `temperature` line of `parameters` from `POST /api/show`. If there is no such line, it records null.

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

`read_file` rules:

- If the path is a folder, return `errors.is_directory`.
- If the path does not exist, return `errors.not_found`.

`list_files` rules:

- It lists one folder. It is not recursive.
- If `path` is missing, the folder is `.`.
- Names are sorted. Folder names end with `/`. Names that start with `.` are hidden.
- The result is one name per line. An empty folder gives an empty result.
- If the path is a file, return `errors.not_a_directory`. If it does not exist, return `errors.not_found`.

`edit_file` rules:

- If `old_str` is empty and the file does not exist, create the file with `new_str`. Create missing parent folders. Return `ok.created`.
- If `old_str` is empty and the file exists, return `errors.already_exists`.
- If `old_str` matches exactly once, replace it. Return `ok.edited`.
- If `old_str` matches zero times, return `errors.old_str_not_found`.
- If `old_str` matches more than once, return `errors.old_str_multiple`.
- If the path is a folder, return `errors.is_directory`. If `old_str` is not empty and the file does not exist, return `errors.not_found`.
- If `old_str` is empty and a parent of the path is a file, return `errors.not_a_directory` for that file, not for the whole path. For `a.py/x`, when `a.py` is a file, `{path}` is `a.py`, spelled as the model sent it. The harness must not crash on this case.

## 8. Tool results

Tool results are plain text. Every error and success string comes from `config/messages.json`.

Truncation: if a tool result is longer than 10,000 characters, the harness keeps the first 10,000 characters. It then adds a new line with `truncated`, where `{n}` is the number of characters cut.
Truncation applies to the whole result text, also to the bash exit code line.

`bash` runs `bash -c <command>` with the working folder as the current folder and a 30-second timeout.
The harness captures stdout and stderr separately. It does not interleave them.
The result is stdout, then stderr, then a final line with `exit_code`.
Each of stdout and stderr that is not empty and does not end with a newline gets one newline. An empty part adds nothing.
For example, `echo out; echo err 1>&2; exit 3` gives `out\nerr\nexit code: 3`. A command with no output gives `exit code: 0`.
If the command times out, the harness kills the command and every process it started. The result is `errors.timeout`.

## 9. Limits

| Limit | Value | Config key |
|---|---|---|
| Turns | 20 | `max_turns` |
| Wall clock, from the first model call | 300 s | `max_seconds` |
| bash timeout | 30 s | none |
| Tool result length | 10,000 characters | none |

If a config key exists, the harness reads the value from the config.

The pilot ran with 40 turns and 600 s. Wave 4 lowered both. In the pilot no passing trial used more than 4 turns, and the failed loops used 40 turns and up to 600 s. The new limits cut the time of a run by more than half. To go back, set `max_turns: 40` and `max_seconds: 600` in `config/baseline.yaml` and in the `limits` of every `task.yaml`.

## 10. Transcript format

`transcript.jsonl` has one JSON object per line, in order. The `type` values are exact.

```json
{"type":"config","config_id":"py.files-bash.local.python.qwen3-8b.no-think","config":{"harness":"py","tools":"files-bash","env":"local","codebase":"python","model":"qwen3:8b","think":false,"num_ctx":32768,"temperature":null,"max_turns":20,"max_seconds":300}}
{"type":"system","content":"You work inside one folder. ..."}
{"type":"user","content":"Fix the bug in parse_date so that ..."}
{"type":"assistant","content":"","tool_calls":[{"id":"call_1_0","name":"read_file","arguments":{"path":"src/dates.py"}}]}
{"type":"tool_result","tool_call_id":"call_1_0","name":"read_file","content":"def parse_date(s):\n    ..."}
{"type":"end","stop_reason":"end_turn","turns":5,"seconds":42.7}
```

- `config` is always the first line. `end` is always the last line. `config` holds every key of the config file as loaded.
- `assistant` has `content`. It has `tool_calls` only if the model made tool calls. It has `thinking` only if Ollama returned a non-empty `thinking`.
- `tool_result` has the result text after truncation, exactly as the model received it.
- If Ollama returns no tool call id, the harness sets the id to `call_<turn>_<index>`.
- `end` has `error` with the error text only if the stop reason is `infra_error`.
- The harness writes each line as soon as it has it, so that a crashed run still has a readable transcript.

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
  "model_digest": "500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41",
  "num_ctx": 32768,
  "temperature": 0.6,
  "think": false,
  "exit_code": 0,
  "tool_calls": 6,
  "malformed_tool_calls": 0,
  "passed": null,
  "grader_output": null
}
```

- `prompt_tokens` and `completion_tokens` are the sums of `prompt_eval_count` and `eval_count` over all model calls in the trial.
- `tool_calls` counts every tool call, malformed calls included.
- `task` is the name of the folder two levels above `--result`. `trial` is the name of the folder one level above, as an integer. If that name is not a number, `trial` is null. This follows the `runs/<config id>/<task>/<trial>/` layout. The eval harness may overwrite both.
- On a harness crash, `turns`, `seconds`, the token counts, and the call counts are 0.
- The eval harness adds one key after grading: `flagged` (bool). See section 12.
- If the harness wrote no `result.json` at all, the eval harness writes one with the keys above, `stop_reason: "infra_error"`, `passed: false`, the process exit code, and `null` for the values it cannot know.
- The eval harness sets `task` to the task folder name, for example `task-01-cart-total`, and `trial` to the trial number.

## 12. Working folder rules

- Every file tool path goes through `safe_path`.
- `safe_path` resolves the path. It follows `..` and symlinks.
- If the resolved path is outside the working folder, the tool returns `errors.outside_folder`.
- Every env receives the host working folder path. The env is responsible for making that folder visible to itself.
- `bash` cannot be limited by path on the laptop (`env: local`). A command can read or write any file that the user can.
- The harness must log every bash command in the transcript.
- The eval harness searches every transcript for `hidden_tests` and `solution`. If it finds either string in a tool call or a tool result, it sets `flagged: true` in `result.json`.
- A flag means "read this trial". It does not mean the agent cheated. The word `solution` also appears in normal code and output.

The env constructor takes the host working folder and `max_seconds` from the config. An env that needs no time limit ignores it.

### `env: docker`

- The env starts one container from the image `barebones-task` (built from `docker/`). If the image does not exist, the harness stops with `infra_error` and names the build command.
- The container mounts the host working folder at `/work`. The container and the host see the same files, so the eval harness grades the host folder.
- The file tools run on the host with the `local` rules. `safe_path` first maps a path that starts with `/work` to the working folder, so that a path which `bash` printed works in a file tool.
- `bash` runs `docker exec <container> timeout --signal KILL 30 bash -c <command>` in `/work`. GNU `timeout` kills the command and every process it started. The result format is the one in section 8. `bash` sees only `/work`, not the other host files.
- Every container gets 2 CPUs and 2 GB of memory, so that runs are comparable.
- The container dies with the harness, also when the harness is killed. Every container name starts with `barebones-`.

### `env: cloud`

- The env creates one E2B sandbox from the template `barebones-agent` (built from `cloud/`). The harness and the model stay on the host. Only the tools act in the sandbox.
- At start, the env uploads the host working folder to `/home/user/work` in the sandbox. While the agent works, the sandbox copy is the source of truth. Every tool acts on it, and the host folder does not change.
- `safe_path` is path logic: it normalizes the path against `/home/user/work` and rejects a path that leaves it. It follows no symlinks, because there is no host folder to resolve against. The sandbox is the boundary.
- `bash` runs `bash -c <command>` in `/home/user/work` in the sandbox, with the 30-second timeout. On a timeout the env kills the command and every process in its group.
- At stop, the env downloads `/home/user/work` and replaces the host working folder with it. A file that the agent deleted in the sandbox is deleted on the host. Build output (`target`, `__pycache__`, `.pytest_cache`, `node_modules`) stays in the sandbox. A member that would land outside the host folder, for example an unsafe symlink, is skipped, with a note on stderr.
- The sandbox timeout is `max_seconds` + 120 seconds. If the harness dies before stop, E2B kills the sandbox at that timeout. A failed start kills the sandbox before the error reaches the loop.

## 13. Checklist for a new harness

- [ ] The flags and defaults match section 2.
- [ ] The exit codes and the stdout status line match section 2.
- [ ] The configuration ID matches section 3 for every axis value.
- [ ] The loop and the stop reasons match section 4.
- [ ] The request body matches section 5, with no extra fields.
- [ ] The message shapes match section 5, including `thinking` sent back.
- [ ] The harness loads the three data files in section 6 and copies no text from them into its code.
- [ ] The tool order matches `sets` in `config/tools.json`.
- [ ] The tool rules in section 7 match, including the `list_files` rules and the `a.py/x` case.
- [ ] Truncation and the bash result format match section 8.
- [ ] The three envs follow section 12: the `/work` mapping and the container life in `docker`, the upload, download, and sandbox timeout in `cloud`.
- [ ] The transcript record types and fields match section 10.
- [ ] `result.json` has exactly the keys in section 11.
- [ ] The baseline configuration on task 01 gives the same result as the Python harness.

## 14. Open points

- Empty assistant message: in the first pilot run, 2 of 30 trials ended with a message that had no content and no tool calls, while Ollama reported 70 to 217 generated tokens. The second run had none. A replay of the same context with the tool parser off gave a well-formed tool call every time. So Ollama drops a tool call that it cannot parse. The harness treats the empty message as `end_turn`, as section 4 says. A later version decides whether an empty message needs its own rule.
- Background jobs in `bash` differ between `local` and `docker`. A command that leaves a job running (`command &`) returns at a different time in each env, and the job can outlive the call in one env and not in the other. No task needs a background job. A later version decides whether the spec needs one rule.
- Experiment 1: the `prompt` config key (section 3) selects the system prompt file. Its default is `config/system_prompt.txt`, so it changes nothing for v1 runs. `config/system_prompt_v2.txt` holds the current prompt plus two rules: read a file before you edit it, and run the tests before you say the change is done. The eval harness flag `--set prompt=config/system_prompt_v2.txt` writes the key into every config file of a run. The configuration ID does not name the prompt, so each prompt version needs its own `--runs` folder. A prompt version is a candidate seventh axis. It is not part of version 1.

## 15. Clarifications (version 1, no behavior change)

These items state what the three harnesses already do. They change no rule.

- (a) "Wall clock" in sections 4 and 9 means the process's monotonic clock. On macOS that clock excludes system sleep in Python and Go and includes it in Node, and the E2B sandbox timeout is real time, so runs need a machine that stays awake.
- (b) JSON whitespace in requests and in transcript lines is free. The values and the key order are fixed.
- (c) In task mode, every child process gets stdin from /dev/null: the eval harness starts each harness with stdin from /dev/null, and each env either passes that stdin on (Python; TypeScript `local`) or sets /dev/null itself (Go; TypeScript `docker`; the sandbox command in `cloud`).
- (d) The `local` and `docker` file tools and `bash` output normalize CRLF to LF, as Python text mode does. The `cloud` env does not.
- (e) The `{detail}` text of `errors.invalid_arguments` is free text. The three harnesses currently keep it identical.
- (f) The eval harness can build a harness before it runs it. It builds the Go harness into `bin/` when the binary is missing or older than a source file.
- (g) The `prompt` key selects the system prompt file. If the key is absent, the harness reads `config/system_prompt.txt`. v1 runs never set it.
- (h) The baseline env is `docker` since 2026-09-25. `local` with a bash tool set runs only with `--allow-local-bash`. No behavior of the harness changed.
