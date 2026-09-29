# Handoff

Read this first, before any other file, if you have not seen this project before.

## What exists

Barebones Agent is a hand-built agent harness (Python, TypeScript, and Go versions) that runs a local model, Qwen3 8B through Ollama, against 30 small software-engineering tasks in three languages. An eval harness (`src/evals/`) starts the agent as a separate process, grades it against hidden tests, and reports pass rates. The project tests 162 configurations across six axes: harness, tool set, env (`local`, `docker`, `cloud`), codebase, model, and thinking mode. The repo structure, the harness, the tasks, and the eval harness are all built and frozen at spec version 1. The project has moved from building the harness to running experiments with it.

## The numbers so far

| Run | Configuration | pass@1 | Notes |
|---|---|---|---|
| Pilot | `py.files-bash.local.python.qwen3-8b.no-think` | 0.100 | 30 trials, on `local`, before the docker switch. `docs/pilot.md`. |
| Wave 4 smoke | 9 Python-harness configs, 3 envs x 3 codebases | mixed | 18 trials, 12 passed, 0 infra errors. `docs/pilot.md`, "After the pilot". |
| Wave 6 harness check | baseline, 3 harnesses, tasks 01 and 07 | mixed | 6 of 6 trials valid, same first-call prompt tokens (527) for all three. |
| Wave 6 stage 2 smoke | 10 stage 2 configs, tasks 01 and 07 | mixed | 20 of 20 trials valid, 10 passed, 0 infra errors. |
| Terminal-Bench 2.1 subset, run 1 | `py.files-bash.harbor.terminal-bench-2-1.qwen3-8b.no-think` | 0.000 | 0 of 20, ran 2026-09-29. 13 end_turn, 4 max_turns, 2 max_seconds, 1 infra_error; no exit-139. `docs/pilot.md`, "Terminal-Bench 2.1 subset, run 1". |

Experiment 1 (prompt v1 or v2, thinking off or on), 30 trials per cell, on `local`:

| Cell | pass@1 | pass@3 | pass^3 | Status |
|---|---|---|---|---|
| v1, thinking off | 0.067 | 0.100 | 0.000 | done (30/30) |
| v2, thinking off | 0.367 | 0.500 | 0.300 | done (30/30) |
| v1, thinking on | 0.433 | 0.700 | 0.100 | done (30/30) |
| v2, thinking on (local, partial) | 0.423 | 0.519 (k=2) | 0.333 (k=2) | stopped at 26/30, 11 passed, kept as history |
| v2, thinking on (docker, full) | 0.333 | 0.500 | 0.200 | 30/30, 10 passed, 208 s per trial; the cell used for comparisons |

Experiment 1 is complete. The prompt and thinking each fix the blind-edit habit and do not add up; the working setting is prompt v2 with thinking off. See `docs/pilot.md`, section "Experiment 1 results", for the full write-up: the v2 prompt removes the blind-first-edit pattern (19 of 30 v1 trials vs. 0 of 30 v2 trials), and shifts the stop reason from `max_turns` to `end_turn`.

Stage 2 (9 configurations, one axis at a time, prompt v2, docker baseline), 30 trials each, ran 2026-09-26: 270 of 270 trials valid, 0 infra errors. Baseline (`py.files-bash.docker.python.qwen3-8b.no-think`) pass@1 0.267; `files`-only scores highest (0.433), `bash`-only lowest (0.167); `typescript` and `rust` codebases both score 0.400, above the `python` baseline; `cloud` env and the `ts`/`go` harnesses match the baseline within noise; thinking on scores 0.333 at 260 s per trial. See `docs/pilot.md`, section "Stage 2 results", for the full table, the axis effects, and the contention audit.

Two levers against the stage 2 baseline, 30 trials each, ran 2026-09-27: 0 infra errors on either.

| Lever | pass@1 | pass^3 | s / trial | Note |
|---|---|---|---|---|
| Lever 1: `tool_errors=rich` | 0.267 -> 0.200 | 0.100 -> 0.000 | 60.3 -> 40.5 | Removes the repeat loop; the model then makes one wrong edit and stops. No gain. |
| Lever 2: `auto_check` (harness runs pytest after each edit) | 0.267 -> 0.400 | 0.100 -> 0.300 | 60.3 -> 83.3 | First lever to raise both the score and the reliability. +0.133 is at the edge of 30-trial noise. |
| Lever 2, confirmation (second 30-trial sample) | 0.267 -> 0.400 | 0.100 -> 0.300 | 60.3 -> 59.3 | Confirms lever 2: pooled with sample 1, auto_check passes 24 of 60 (0.400) against baseline 8 of 30 (0.267). |
| Lever 3: `files` tools + `auto_check` | 0.433 -> 0.500 | 0.200 -> 0.500 | 46.0 -> 58.0 | Best measured configuration so far. Ran 2026-09-27, 30/30 trials, 0 infra errors. |

See `docs/pilot.md`, section "Lever experiments", for the per-task table and both readings.

The Harbor smoke ran one task, `write-compressor`, from Terminal-Bench 2.1 (2026-09-27/28): the chain works end to end (image pull, agent run in the container, verifier, reward), 1/1 trial, 0 infra errors. The agent stopped at 3 turns and 8.3 seconds (`end_turn`, well under the 20-turn / 300-second budget), tried piping the input file through the decompressor (which segfaulted under container CPU emulation), then wrote an empty output file and stopped. The verifier passed 2 of 3 hidden tests but gave a reward of 0. See `docs/pilot.md`, section "Harbor smoke", for the full write-up and the checklist for the 20-task subset.

The 20-task Terminal-Bench 2.1 subset ran 2026-09-29, 03:27 UTC to 11:58 local: 0 of 20, 0 infra errors beyond the 1 model-degenerate trial counted below, no exit-139. Stops: 13 `end_turn`, 4 `max_turns`, 2 `max_seconds`, 1 `infra_error` (`dna-assembly`, an Ollama 500 "token repeat limit reached" before turn 1). Failure patterns: claimed done with no way to check the work (6), repeat loop that hit a limit while still stuck (5), gave up after a few failed tries (3), stuck reading or listing the same files (2), asked the user against the system prompt's rule (2), model degenerated (1), empty reply with no tool call (1). About 11.6 of the run's 12.5 hours came from 4 tasks (1 to 4 hours each) where a Mac sleep overnight and qemu (`amd64`-on-`arm64`) emulation dominated the wall clock; the other 16 tasks took 46 to 852 seconds each. See `docs/pilot.md`, section "Terminal-Bench 2.1 subset, run 1", for the per-task table, the pattern table with quotes, and the three conclusions.

## Decisions and their dates

| Date | Decision | Why |
|---|---|---|
| 2026-09-23 (pilot) | Limits are `max_turns: 20`, `max_seconds: 300` (the pilot used 40 and 600) | No passing pilot trial used more than 4 turns; failed loops burned the whole budget. |
| 2026-09-23 (pilot) | Every Python task gets an empty `conftest.py` in `repo/` and `solution/` | A bare `pytest` failed to import the module under test. |
| 2026-09-24 | `config/system_prompt_v2.txt` adds two lines to the system prompt: read before you edit, run the tests before you say you are done | Tests what the pilot's two failure patterns are worth. |
| 2026-09-25 | The baseline env is `docker`, not `local` | `bash` is not fenced on `local`; `docker` and `cloud` isolate it. |
| 2026-09-25 | `run.py` blocks `env: local` with a `bash` or `files-bash` tool set, unless `--allow-local-bash` is passed | Same reason. `files` alone is still safe on `local`, because `safe_path` fences the file tools. |

## The queue

`experiments.yaml`, at the repo root, is the one place that lists every experiment: past and future, with its status, its exact command, its trial count, its time estimate, what it needs (Ollama, Docker, E2B, and E2B cost), how to tell it is done, and its results folder.

## The three scripts

| Script | What it does |
|---|---|
| `scripts/preflight.sh` | Checks the machine before a run: lid, power, Ollama, Docker, the E2B key, toolchains, disk space, load, the coordinator lock, and any leftover containers or processes. Fails only on disk under 15 GB; everything else is a warning. |
| `scripts/run.sh <experiment-id>` | Looks up the experiment in `experiments.yaml`, refuses unless it is `ready` (or `--force`), runs preflight, takes the coordinator's heavy lock, runs the command, always releases the lock, then prints the report. `--dry-run` does everything except the command. |
| `scripts/status.sh` | Prints every experiment's status, trials done versus expected, its report line if done, the lock state, and any running containers or processes. |
| `src/evals/report.py --compare <baseline-dir> <experiment-dir>` | Prints a per-task pass table and a pass@1/pass^k/seconds/turns summary, baseline against an experiment, for each configuration present in both folders. |
| `src/evals/analyze.py <runs-dir>` | Prints stop reasons, tool call counts, bash and test-command use, and failure patterns (blind first edit, repeat loops, claimed-done-but-failed, limit hits) per configuration. |

## Resource facts

- Machine: Apple M4, 24 GB RAM, 10 cores. One Ollama daemon, `qwen3:8b` (7.7 GB while loaded), one request at a time.
- Docker Desktop VM: 10 CPU / 8 GB. Each trial container is 2 CPU / 2 GB, named `barebones-<hex>`.
- E2B template `barebones-agent`: 2 vCPU / 2 GB, about $0.13/hour, $100 credit, about $0.15 used as of 2026-09-25.
- Two other projects share this machine. The coordinator serializes HEAVY jobs with the lock in `.coord/PROTOCOL.md`.
- Measured seconds per trial: thinking off with the v1 prompt, about 139 s; thinking off with the v2 prompt, about 45 s; thinking on, about 200 to 220 s. A trial cannot exceed 300 s plus grading.

## Sleep and lid rule

Run every model job on power, with the lid open. System sleep stretches every timer: the Node clock counts sleep time, the E2B sandbox timeout is real time, and a sandbox or a long trial can die in the middle. `scripts/run.sh` starts every command with `caffeinate -i` inside the command string in `experiments.yaml`, but that alone does not open the lid.

## The coordinator protocol

Read `.coord/PROTOCOL.md` before any Ollama, Docker-heavy, or E2B run. Take the heavy lock before you start. Only start a HEAVY job after the coordinator sends "GO \<job\>".

## What is waiting on whom

- Experiment 1 ended on 2026-09-25 at 19:18. Stage 2 ended 2026-09-26 at 23:00 UTC, 270 of 270 trials valid, 0 infra errors. Both locks are released.
- Lever 1, lever 2, the lever 2 confirmation, lever 3, and the Harbor smoke all ended 2026-09-27/28, 0 infra errors. All locks are released.
- `harbor-terminal-bench-2.1-subset`, the 20-task Terminal-Bench 2.1 subset, ended 2026-09-29 at 11:58 local (about 12.5 hours, mostly sleep and qemu on 4 tasks). 0 of 20; see `docs/pilot.md`, "Terminal-Bench 2.1 subset, run 1", for the per-task table and the failure patterns. The lock is released.
- What is waiting on whom for `harbor-tb21-run2` (the next GO candidate): three LIGHT code changes, no GO needed to make them:
  1. Raise the Harbor `bash` timeout from 30 s to 120 s in `src/harness/python/env/harbor.py` (`env: harbor` only).
  2. Write `config/system_prompt_v3.txt`: prompt v2 plus a line telling the model to keep going instead of stopping to ask (5 of 20 subset trials asked the user or gave up).
  3. Set the Harbor budget to 40 turns / 600 seconds awake, under `HARBOR_WALL_SECONDS`'s 10-minute real-time cap (Terminal-Bench's own per-task default is 900 s; our 300 s is well under it).
  Once those three land, `harbor-tb21-run2` needs the coordinator's GO. See `docs/OPEN-QUESTIONS.md`, 2026-09-29, and `experiments.yaml`, entry `harbor-tb21-run2`, for the exact command.
- Waiting on the owner: whether to adopt `files` + `auto_check` as the working setting for the private suite (`config/baseline.yaml` would get `tools: files` and `auto_check: python -m pytest -q tests`, one line each, but it moves the frozen baseline). See `docs/OPEN-QUESTIONS.md`, 2026-09-27, "Lever 3".
- The lever 1 (`tool_errors`), lever 2 (`auto_check`), and Harbor adapter (`env: harbor`) builds are merged into `main`. `tool_errors` picks the `edit_file` error format (`plain` or `rich`, Python harness only). `auto_check` runs a shell command after a successful `edit_file` and appends its output (Python harness only). Both keys default to null/absent, byte-identical to today's behavior. See `docs/harness-spec.md`, section 15, items (i) and (j), and `docs/harbor.md`.
- To read a finished lever run: `uv run python src/evals/report.py --compare <baseline-dir> <experiment-dir>` for the per-task pass table and the pass@1/pass^k/seconds/turns summary, and `uv run python src/evals/analyze.py <experiment-dir>` for stop reasons, tool calls, and failure patterns (repeat loops, claimed-done-but-failed).
- `docs/OPEN-QUESTIONS.md` lists the decisions taken by default so far (the partial cell, the stage 2 prompt version, the thinking-mode time limit, the local/bash grid question, the E2B spending approval, the contention audit, the docker/local baseline gap, the `files`-only finding, and the two lever results). None of them block a run; the coordinator can revisit any of them at any time.

## How to start and resume a run

A full run lasts hours, longer than one shell command in a Claude session can wait. Start it detached, then watch it:

```
nohup scripts/run.sh <experiment-id> > runs/<results-folder>/console.log 2>&1 &
scripts/status.sh
```

`scripts/run.sh` takes the coordinator's heavy lock, runs the command under `caffeinate -i`, and releases the lock when the run ends or is killed.

Every run is safe to repeat: the eval harness skips a trial that already has a graded `result.json`. To resume a stopped or partial run, start the same experiment again with the same command. Nothing needs to be cleaned up first. To stop a run, kill the `run.sh` process; the trap releases the lock, and the harness kills its own container.
