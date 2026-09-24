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
