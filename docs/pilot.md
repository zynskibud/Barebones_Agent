# Pilot: stage 1 on the baseline

Date: 2026-09-23. Machine: Apple M4, 24 GB. Ollama 0.34.3, `qwen3:8b` (Q4_K_M, digest `500a1f06...`).
Configuration: `py.files-bash.local.python.qwen3-8b.no-think`. Limits: 40 turns, 600 seconds, `num_ctx` 32768, temperature 0.6 (the model default).
Suite: the 10 Python tasks, 3 trials each, one after another.

Wave 2 ran stage 1 twice. The first run gave the failure groups and the fix list below. The second run started from an empty `runs/` folder on the final code. The numbers in this file come from the second run.

## Result

| Metric | Value |
|---|---|
| Trials | 30 (10 tasks × 3) |
| Passed | 3 |
| pass@1 | 0.100 |
| pass@3 | 0.200 |
| pass^3 | 0.000 |
| Time per solved task | 2288.9 s |
| Mean turns per trial | 22.7 |
| Mean prompt tokens per trial | 49,995 |
| Mean completion tokens per trial | 1,868 |
| Mean seconds per trial | 228.9 |
| Total wall time for 30 trials | 6881 s (1 h 55 min) |
| Flagged trials | 0 |
| Infra errors | 0 |
| Stop reasons | `end_turn` 13, `max_turns` 13, `max_seconds` 4 |

The plan sets a bar of about 20% pass@1 for stage 2. The baseline scores 10%. It is below the bar.

The first run gave the same score: 3 of 30, with 252.7 s per trial and 7584 s of wall time. Both runs passed only task 01 and task 07.

## Per task

| Task | Trial | Result | Stop reason | Turns | Seconds |
|---|---|---|---|---|---|
| task-01-cart-total | 1 | pass | end_turn | 4 | 26.9 |
| task-01-cart-total | 2 | fail | end_turn | 4 | 16.1 |
| task-01-cart-total | 3 | fail | end_turn | 4 | 18.0 |
| task-02-billing-month-end | 1 | fail | end_turn | 3 | 29.7 |
| task-02-billing-month-end | 2 | fail | end_turn | 3 | 24.5 |
| task-02-billing-month-end | 3 | fail | end_turn | 6 | 83.9 |
| task-03-ticket-search-empty | 1 | fail | max_turns | 40 | 250.4 |
| task-03-ticket-search-empty | 2 | fail | max_turns | 40 | 256.1 |
| task-03-ticket-search-empty | 3 | fail | max_turns | 40 | 253.1 |
| task-04-settings-parser-spaces | 1 | fail | max_turns | 40 | 149.8 |
| task-04-settings-parser-spaces | 2 | fail | max_turns | 40 | 129.7 |
| task-04-settings-parser-spaces | 3 | fail | max_seconds | 30 | 600.0 |
| task-05-textstats-word-count | 1 | fail | end_turn | 18 | 107.1 |
| task-05-textstats-word-count | 2 | fail | max_turns | 40 | 204.9 |
| task-05-textstats-word-count | 3 | fail | max_turns | 40 | 204.4 |
| task-06-menu-sort-by-price | 1 | fail | max_turns | 40 | 234.1 |
| task-06-menu-sort-by-price | 2 | fail | max_turns | 40 | 233.4 |
| task-06-menu-sort-by-price | 3 | fail | max_turns | 40 | 245.1 |
| task-07-inventory-negative-price | 1 | pass | end_turn | 4 | 40.8 |
| task-07-inventory-negative-price | 2 | pass | end_turn | 4 | 38.6 |
| task-07-inventory-negative-price | 3 | fail | max_turns | 40 | 288.3 |
| task-08-expense-report-largest | 1 | fail | max_turns | 40 | 595.9 |
| task-08-expense-report-largest | 2 | fail | end_turn | 24 | 396.8 |
| task-08-expense-report-largest | 3 | fail | max_turns | 40 | 576.0 |
| task-09-payroll-split-function | 1 | fail | max_seconds | 28 | 600.0 |
| task-09-payroll-split-function | 2 | fail | max_seconds | 9 | 600.0 |
| task-09-payroll-split-function | 3 | fail | max_seconds | 9 | 600.0 |
| task-10-slug-rename | 1 | fail | end_turn | 4 | 21.7 |
| task-10-slug-rename | 2 | fail | end_turn | 4 | 21.2 |
| task-10-slug-rename | 3 | fail | end_turn | 4 | 20.2 |

No trial was flagged. No trial read `hidden_tests/` or `solution/`.

## Failure groups

Every failed trial went into one group.

| Group | Count | Example |
|---|---|---|
| Harness bug | 0 | none |
| Eval harness bug | 0 | none |
| Task defect | 0 | none |
| Model behavior | 27 | task-03 trial 1: 40 identical `edit_file` calls with a guessed `old_str`, no `read_file` |

A check script compared every trial to the spec. It checked these points:

- `config` is the first transcript line and `end` is the last.
- Each tool call has one tool result, in call order.
- `turns` equals the number of assistant records.
- `tool_calls` equals the number of tool results.
- The exit code matches the stop reason.
- `result.json` has exactly the spec keys plus `flagged`.

It found 0 problems in 30 trials. The eval harness killed no trial. Task-02 trial 3 had 2 malformed calls (a missing required argument). The harness returned the spec error string, counted them, and went on, as section 4 says.

The report math was checked by hand. pass@1 = 3 / 30. pass@3: task 01 and task 07 each give 1.0, the other tasks give 0, so the mean is 0.2. pass^3: no task passed 3 times, so 0.

The 27 model behavior failures fall into five patterns:

| Pattern | Trials | Example |
|---|---|---|
| Blind edit loop. No read. The model sends `edit_file` with a guessed `old_str`. The error comes back. The model sends the same call again until a limit stops it. | 15 | task-06 trial 1: 40 × `edit_file` with `old_str` `def menu():`, 40 × `old_str not found` |
| Loop after a read. The model reads the file, then writes an `old_str` with one extra indent level, as if the function sat in a class. It repeats that call until the clock stops it. | 2 | task-09 trial 2: 1 read, 8 identical edits, 600 s |
| Gave up. Blind edits, then a message that asks the user to check the files. Nobody answers. | 2 | task-08 trial 2: 46 failed edits, then "Please check the file names and content." |
| Wrong code, claimed done, no check. | 5 | task-01 trial 2: added a commented-out line after `return total`. task-02 trial 1: assigned to `start.day` on a `date` object. |
| Partial work, claimed done, no check. | 3 | task-10 trial 1: renamed the `def` line only, left every other use of `mk_slug` in three files |

The 17 loop trials used 6021 s of the 6867 s of trial time (88%). No passing trial used more than 4 turns.

The prompts of tasks 02 to 09 name the file. In those tasks the model skips `list_files` and `read_file` and edits blind. In task 01 and task 10, the prompt names no file, and the model lists and reads first.

### The empty reply

In the first run, 2 of 30 trials ended with an assistant message that had no content and no tool calls. The second run had none. The harness reads that message as `end_turn`, as the spec says. A replay of one such context through Ollama, with the same messages and tools, gave an empty message again in some rounds, with 70 to 217 generated tokens. A replay with the tools written into the system prompt and the Ollama tool parser off gave a well-formed `edit_file` call 8 times out of 8. So Ollama drops a tool call that it cannot parse, and the harness never sees it. The spec lists this as an open point (section 14).

## Fixes in this wave

| File | Change | Why |
|---|---|---|
| `src/harness/python/model.py` | `Model.chat` takes a per-call `timeout`. A timeout raises `ModelTimeout`, a subclass of `ModelError`. | The loop must tell a timeout apart from other failures. |
| `src/harness/python/loop.py` | Each model call gets `max_seconds` minus the elapsed time, with a floor of 1 second. A `ModelTimeout` stops the loop with `max_seconds`. | Before this, one run could last almost 2 × `max_seconds`, and a slow call was an `infra_error`. |
| `docs/harness-spec.md` | Section 4 step 3 and section 5 state the per-call timeout rule. The timing item left section 14. Section 14 gained the empty-reply open point. | The spec is the contract. |

The eval harness, the tasks, the system prompt, and the tool definitions did not change. `--validate-tasks` passes for all 10 tasks. The 21 eval harness tests pass.

The timeout fix was checked with `max_seconds: 2` on task 01. Turn 1 returned, the second call got a 1-second timeout, and the run stopped with `max_seconds` at 2.3 seconds, exit code 2. In the pilot, 4 trials stopped with `max_seconds` at 600.0 s, and none ran past it.

## Tool use

| Tool | Calls in 30 trials |
|---|---|
| `edit_file` | 753 |
| `read_file` | 13 |
| `list_files` | 6 |
| `bash` | 0 |

The first call was `edit_file` in 20 trials, `list_files` in 6, and `read_file` in 4. Ten trials read a file before the first edit. No trial ran a command. No trial ran the tests in `tests/`.

The three passes took 4 turns each. Task 01 trial 1 listed, read, and edited. The two task-07 passes sent one blind edit, got the error, read the file, and then edited the right lines. So the model can recover from a bad first guess. It did so in 2 of 20 blind starts.

## Two patterns that matter for the next waves

1. **The model edits before it reads.** When the prompt names the file, the model skips `read_file` and sends `edit_file` with an `old_str` that it guessed. The guess does not match. The model then repeats the same call until a limit stops it. This one pattern explains 17 of 27 failures and 88% of the wall time. Stage 2 will show whether the `files` tool set, the `bash` tool set, or `think: true` changes this.
2. **The model never checks its work.** No trial ran `bash`. No trial ran a test. Every `end_turn` failure came with a claim of success or a request to the user. The `bash` tool set leaves the model no other tool, so stage 2 will show whether it tests when it must.

## What the score means

The score is far below the bar. The reason is not task difficulty. Each task needs a change of 1 to 8 lines in one or two files, and the model wrote a correct change in 3 trials. In 17 of 27 failures the model never made one valid edit, because it did not look at the file. In 8 more it looked, edited, and did not check. So the limit is the tool use of this model in this mode, not the tasks. With `think: false` and this tool set, `qwen3:8b` is too weak at tool use for the suite. Two axes of the grid test the cheap fixes for that: `think` and `tools`. This wave changed no task, prompt, or system prompt.

## Watch items for later waves

- `pytest` alone fails to import the module under test in every Python task repo (no `conftest.py`, no `pyproject.toml`). `python -m pytest` works. No trial hit this, because no trial ran a command. The `bash` tool set will hit it. On the laptop, GNU `sed -i` syntax fails as well. In Docker it works. So the `env` axis will change what `bash` can do.
- Task 06: the hidden test `test_returns_the_same_item_dicts` needs the same dict objects in the new list. A deep copy fails it. No trial got that far.
- Task 10: the hidden test `test_old_name_is_gone_from_every_source_file` fails on a comment that mentions `mk_slug`. No trial got that far.
- Ollama drops a tool call that it cannot parse and returns an empty message (see above).
- Time: one configuration takes about 2 hours on this Mac. Stage 2 (10 configurations) takes about 20 hours. The full grid takes about 14 days at this rate. No passing trial used more than 4 turns, and the loops use 40. A lower `max_turns` cuts the wall time. Decide that before stage 2, because `think: true` and other tool sets can need more turns.

## Raw data

`runs/py.files-bash.local.python.qwen3-8b.no-think/` holds the 30 trial folders of the second run, each with `prompt.txt`, `harness.log`, `transcript.jsonl`, and `result.json`. `runs/report.json` holds the table. The folder is not in git.

## After the pilot

Two decisions, applied in wave 4. Each one is one line to revert.

| Decision | Value | Reason | Revert |
|---|---|---|---|
| Limits | `max_turns: 20`, `max_seconds: 300` (pilot: 40 and 600) | No passing trial used more than 4 turns. The failed loops burned all 40 turns and up to 600 s. | Set the two keys back in `config/baseline.yaml` and in every `task.yaml`. |
| `conftest.py` | An empty file in every Python task `repo/` and `solution/` | A bare `pytest` failed to import the module under test, while `npm test` and `cargo test` worked out of the box. | Delete the 20 files. |

Wave 4 smoke run: the Python harness across the 3 envs and the 3 codebases, 2 tasks × 1 trial each. 18 of 18 trials valid, 12 passed, 0 infra errors, 0 flagged, no leftover containers or sandboxes. Every failure is model behavior.

| Config (`py.files-bash.<env>.<codebase>.qwen3-8b.no-think`) | Task 01 | Task 07 |
|---|---|---|
| local.python | pass, end_turn, 20.6 s | fail, max_turns, 109.6 s |
| local.typescript | pass, end_turn, 13.0 s | pass, end_turn, 13.4 s |
| local.rust | fail, end_turn, 11.6 s | pass, end_turn, 13.1 s |
| docker.python | pass, end_turn, 20.1 s | fail, max_turns, 130.3 s |
| docker.typescript | fail, end_turn, 12.5 s | pass, end_turn, 15.6 s |
| docker.rust | fail, end_turn, 12.2 s | pass, end_turn, 13.7 s |
| cloud.python | pass, end_turn, 18.3 s | pass, end_turn, 31.4 s |
| cloud.typescript | pass, end_turn, 13.2 s | pass, end_turn, 16.3 s |
| cloud.rust | fail, end_turn, 13.1 s | pass, end_turn, 14.1 s |

The grader used `pytest`, `node --test`, or `cargo test` in every env. The Rust task 01 failures are code that does not compile. With the new limits, a failed loop costs about 110 to 130 s instead of 250 s.

## After wave 6

Date: 2026-09-24. Same machine, same Ollama, same model digest. Limits: 20 turns, 300 seconds.

### Harness check

The baseline configuration ran with each of the three harnesses on tasks 01 and 07, 1 trial each, into `runs/smoke/`. The model is random (temperature 0.6), so pass or fail can differ between harnesses. What must match did match:

- Every trial is valid against the spec check list (the same six checks as the pilot). 0 problems in 6 trials.
- The same record types in every transcript: `config`, `system`, `user`, `assistant`, `tool_result`, `end`.
- The same `result.json` keys, in the same order.
- The same `config` line, except the `harness` value. The Python harness writes JSON with a space after each comma and colon, and the other two write compact JSON. The values and the key order are equal (spec section 15, item b).
- The same `prompt_tokens` on the first model call: 527 for each harness. Ollama reports the same count for a cached and an uncached prompt, so the count depends only on the request. Measured with `max_turns: 1` on task 01, outside `runs/`.

| Harness (`<h>.files-bash.local.python.qwen3-8b.no-think`) | Task 01 | Task 07 | First-call prompt tokens |
|---|---|---|---|
| `py` | pass, end_turn, 4 turns, 14.1 s | fail, max_turns, 20 turns, 112.7 s | 527 |
| `ts` | pass, end_turn, 4 turns, 19.3 s | pass, end_turn, 4 turns, 30.5 s | 527 |
| `go` | pass, end_turn, 4 turns, 32.8 s | fail, max_turns, 20 turns, 207.7 s | 527 |

On task 01 all three harnesses used 4 turns and 2,817 prompt tokens in total. The two task 07 failures are the blind edit loop from the pilot: 20 × `edit_file`, 20 × `old_str not found`, no `read_file`.

The seconds differ because the machine slowed down, not because of the harness. The Ollama log shows the same 200-token turns at 5.5 s during the Python trial and at 8 to 11 s during the Go trial, which ran last, with prompt processing down from about 150 to about 70 tokens per second. A rerun of task 01 with the harnesses interleaved gave `py` 12.0 s, `go` 9.7 s, and `ts` 9.9 s. So one trial's seconds carry a machine-state error of about 2×. Compare time across harnesses only over many trials, in the same session.

### Stage 2 smoke

The 10 stage 2 configurations ran tasks 01 and 07, 1 trial each, into `runs/smoke/`. The suite skipped the six trials of the harness check as done. 20 of 20 trials are valid, 10 passed, 0 flagged, 0 infra errors in the final results. The first pass of the `docker` configuration gave 2 infra errors: Docker Desktop was not running. Nothing in the harness or the eval harness changed. Docker Desktop was started, and the two docker trials ran again. No container and no sandbox stayed alive.

| Configuration | Task 01 | Task 07 | Seconds | Notes |
|---|---|---|---|---|
| `py.files.local.python.qwen3-8b.no-think` | fail, max_turns, 20 turns, 189.4 s | fail, max_turns, 20 turns, 120.9 s | 310.3 | Task 01: one list, two reads, then 17 × `edit_file` with a wrong `old_str`. Task 07: 20 blind edits, no read. |
| `py.bash.local.python.qwen3-8b.no-think` | fail, end_turn, 2 turns, 9.6 s | fail, end_turn, 6 turns, 36.3 s | 45.9 | Task 01: one `echo`, then a question to the user. Task 07: GNU `sed -i` syntax, which fails on macOS, then an `echo >>` that left an `IndentationError`. |
| `py.files-bash.local.python.qwen3-8b.no-think` | pass, end_turn, 4 turns, 14.1 s | fail, max_turns, 20 turns, 112.7 s | 126.8 | The baseline, from the harness check. Task 07: 20 blind edits. |
| `py.files-bash.local.python.qwen3-8b.think` | pass, end_turn, 4 turns, 55.4 s | fail, end_turn, 3 turns, 73.1 s | 128.5 | Thinking on every turn, 300 to 1,200 characters each, about 4× the time per turn. Task 07: read, one edit with a literal `\n` in the code (`SyntaxError`), claimed done. |
| `py.files-bash.local.typescript.qwen3-8b.no-think` | fail, end_turn, 4 turns, 10.6 s | pass, end_turn, 3 turns, 14.9 s | 25.5 | Task 01: wrong code ("multiplies the total by 1"), claimed done. |
| `py.files-bash.local.rust.qwen3-8b.no-think` | fail, max_turns, 20 turns, 97.6 s | pass, end_turn, 3 turns, 13.4 s | 111.0 | Task 01: list, read, then 18 × `edit_file` with a wrong `old_str`. |
| `py.files-bash.docker.python.qwen3-8b.no-think` | pass, end_turn, 4 turns, 60.8 s | pass, end_turn, 4 turns, 106.2 s | 167.0 | Rerun after the Docker Desktop start. The model generated at about 9 tokens per second right after that start, against about 35 before. Wave 4 measured 20.1 s for the same task 01 trial. |
| `py.files-bash.cloud.python.qwen3-8b.no-think` | pass, end_turn, 4 turns, 27.1 s | fail, max_seconds, 15 turns, 300.0 s | 327.1 | Task 07: one read, then 14 edits with a wrong `old_str`. The clock stopped it before the turn limit. |
| `ts.files-bash.local.python.qwen3-8b.no-think` | pass, end_turn, 4 turns, 19.3 s | pass, end_turn, 4 turns, 30.5 s | 49.8 | From the harness check. |
| `go.files-bash.local.python.qwen3-8b.no-think` | pass, end_turn, 4 turns, 32.8 s | fail, max_turns, 20 turns, 207.7 s | 240.5 | From the harness check. Task 07: 20 blind edits. |

Every failure is model behavior. The patterns are the ones from the pilot: the blind edit loop (5 trials), wrong code claimed done (3 trials), and a question to the user (1 trial). Two new facts for stage 2:

- The `bash` set on the laptop hits the macOS `sed`. The model writes GNU `sed -i 's/a/b/'`, which BSD `sed` rejects. In `docker` and `cloud` the same command works. So the `env` axis changes what the `bash` set can do, as the pilot predicted.
- Thinking makes each turn about 4× slower and did not stop the wrong-code pattern in 1 of 2 trials.

The wave 5 smoke folders for `ts` on `docker` and `cloud` held two stale failures from a session in which the Mac slept (858 s wall clock, and a sandbox that E2B killed). Both ran again: task 01 passed on both, 46.7 s and 50.8 s.

### Time estimates

Seconds per trial in this smoke, by thinking mode:

| Mode | Trials | Mean s per trial | Median s per trial |
|---|---|---|---|
| no-think | 18 | 78.0 | 34.6 |
| think | 2 | 64.2 | 64.2 |

From these means: stage 2 (270 no-think trials + 30 think trials) takes about 6.4 hours. The full grid (2,430 + 2,430) takes about 96 hours (4 days). Experiment 1 (60 + 60) takes about 2.4 hours.

These means are low for two reasons. The smoke ran only tasks 01 and 07, the two tasks that the pilot passed. And only 2 thinking trials ran, both short. In the pilot 17 of 30 trials hit a limit. In this smoke a trial that hit a limit cost 171 s on average (97.6 to 300.0 s), and a trial that stopped on its own cost 31 s. With the pilot's share of limit hits (57%), a no-think trial costs about 111 s. A thinking turn takes about 14 s, so a thinking trial that loops hits the 300 s clock, and a thinking trial costs about 198 s. With these numbers: stage 2 about 10 hours, the full grid about 210 hours (9 days), Experiment 1 about 5 hours.

Plan with these ranges: stage 2, 6 to 10 hours. The full grid, 4 to 9 days. Experiment 1, 2.5 to 5 hours.

## Experiment 1: prompt × thinking

The pilot showed two patterns: the model edits before it reads, and it never checks its work. Experiment 1 measures what two prompt sentences and thinking mode are each worth. It is a 2 × 2 on the baseline configuration (`py`, `files-bash`, `local`, `python`, `qwen3-8b`): the system prompt (v1 = the current prompt, v2 = the current prompt plus two rules) crossed with thinking (off, on). Each cell runs the 10 Python tasks × 3 trials.

| Prompt | Thinking off | Thinking on |
|---|---|---|
| v1 (current) | 30 trials (= the pilot, rerun at the new limits) | 30 trials |
| v2 (current + 2 rules) | 30 trials | 30 trials |

The v2 prompt is `config/system_prompt_v2.txt`: the current prompt with these two lines appended as lines 7 and 8, exactly as written here:

```
Before you edit a file, read it.
Before you say the change is done, run the tests.
```

Metrics: pass@1, pass^3, time per solved task, and mean turns. Status: complete on 2026-09-25. Three cells ran on `env: local`. The fourth cell, v2 with thinking on, stopped at 26 of 30 on `local` and then ran in full on `env: docker`, because the baseline env moved to `docker` on 2026-09-25 (see `docs/harness-spec.md`, section 15, item h). See "Experiment 1 results" below for the numbers.

## Experiment 1 results

Date: 2026-09-24. Same machine, same Ollama, same model digest as the pilot. Configuration: the baseline (`py`, `files-bash`, `local`, `python`, `qwen3-8b`) with `prompt` set to v1 or v2 and `think` set to false or true. Limits: 20 turns, 300 seconds. Numbers are from `uv run python src/evals/report.py --runs runs/exp1/<cell>`.

| Cell | Trials | pass@1 | pass@3 | pass^3 | s/solved | Mean turns | Mean seconds | Notes |
|---|---|---|---|---|---|---|---|---|
| v1, thinking off | 30 | 0.067 | 0.100 | 0.000 | 2091.6 | 14.2 | 139.4 | done |
| v2, thinking off | 30 | 0.367 | 0.500 | 0.300 | 121.9 | 6.2 | 44.7 | done |
| v1, thinking on | 30 | 0.433 | 0.700 | 0.100 | 500.4 | 3.3 | 216.9 | done |
| v2, thinking on (local, partial) | 26 | 0.423 | 0.519 (k=2) | 0.333 (k=2) | 494.3 | 3.1 | 209.1 | local, 26 of 30, 11 passed, kept as history |
| v2, thinking on (docker, full) | 30 | 0.333 | 0.500 | 0.200 | 624.2 | 3.0 | 208.1 | docker, 30 of 30, 10 passed; 16 end_turn, 14 max_seconds; the cell used for comparisons |

### First tool call

In the two thinking-off cells (30 trials each), the very first tool call of the trial:

- v1 (current prompt): `edit_file` 19 of 30 trials, `list_files` 6, `read_file` 5. Most trials guess at a file before looking at it.
- v2 (current prompt + 2 rules): `read_file` 15 of 30 trials, `list_files` 15, `edit_file` 0. No trial guesses first.

The one line "Before you edit a file, read it." removed every blind first edit.

### Stop-reason shift

| Cell | end_turn | max_turns | max_seconds |
|---|---|---|---|
| v1, thinking off | 8 | 17 | 5 |
| v2, thinking off | 25 | 4 | 1 |
| v1, thinking on | 16 | 0 | 14 |
| v2, thinking on (26 trials) | 15 | 0 | 11 |

With thinking off, v1 mostly runs out of turns (17 of 30). v2 mostly stops on its own (25 of 30). With thinking on, no trial ever runs out of turns; the model that thinks either finishes in a few turns or spends the whole clock on one long turn, so trials instead run out of time (14 of 30 for v1, 11 of 26 for v2).

### Conclusions

- The two-line prompt change is worth more than it costs. It removes the blind-edit loop and raises pass@1 from 0.067 to 0.367 with thinking off, for no extra time per trial (139.4 s down to 44.7 s, because there is less looping).
- Thinking on raises pass@1 further, but costs about 4 to 5 times the seconds per trial and turns `max_seconds` into the main stop reason. v1-think (0.433) already beats v2-nothink (0.367), and the partial v2-think cell (0.423) is close to v1-think, not clearly above it. So the prompt change and thinking mode do not stack: most of the value with thinking on comes from thinking itself, not from the prompt. The full v2-think rerun in `docker` confirmed it: 0.333, below v1-think (0.433) and below v2-nothink (0.367). Per task it solved 01 and 06 three times each, 09 twice, 04 and 07 once, and 02, 03, 05, 08, 10 never.

**Conclusion of Experiment 1.** The two prompt sentences and thinking mode each fix the blind-edit habit, and they do not add up. The best cell by cost is prompt v2 with thinking off: pass@1 0.367 at 45 s per trial and 122 s per solved task. Thinking on reaches a few more tasks at least once (pass@3 0.70 with v1) but costs 4 to 5 times the time and hits the 300 s limit in 14 of 30 trials in both prompt versions, so its numbers are a lower bound under this limit. The working setting for stage 2 and the lever experiments is prompt v2 with thinking off; thinking stays an axis.
