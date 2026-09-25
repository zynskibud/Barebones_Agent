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

Experiment 1 (prompt v1 or v2, thinking off or on), 30 trials per cell, on `local`:

| Cell | pass@1 | pass@3 | pass^3 | Status |
|---|---|---|---|---|
| v1, thinking off | 0.067 | 0.100 | 0.000 | done (30/30) |
| v2, thinking off | 0.367 | 0.500 | 0.300 | done (30/30) |
| v1, thinking on | 0.433 | 0.700 | 0.100 | done (30/30) |
| v2, thinking on | 0.423 | 0.519 (k=2) | 0.333 (k=2) | **partial**, stopped at 26/30, 11 passed |

The full v2-thinking-on cell reruns in `docker`, into `runs/exp1/v2-think-docker`, as its own experiment. See `docs/pilot.md`, section "Experiment 1 results", for the full write-up: the v2 prompt removes the blind-first-edit pattern (19 of 30 v1 trials vs. 0 of 30 v2 trials), and shifts the stop reason from `max_turns` to `end_turn`.

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

- Waiting on the coordinator: "GO exp1-v2-think-docker", to run the queued rerun of the v2-thinking-on cell in `docker`.
- After that: "GO stage2-v2-docker", the one-axis-at-a-time measurement with the v2 prompt.
- `docs/OPEN-QUESTIONS.md` lists the decisions taken by default so far (the partial cell, the stage 2 prompt version, the thinking-mode time limit, the local/bash grid question, and the E2B spending approval). None of them block a run; the coordinator can revisit any of them at any time.

## How to start and resume a run

A full run lasts hours, longer than one shell command in a Claude session can wait. Start it detached, then watch it:

```
nohup scripts/run.sh <experiment-id> > runs/<results-folder>/console.log 2>&1 &
scripts/status.sh
```

`scripts/run.sh` takes the coordinator's heavy lock, runs the command under `caffeinate -i`, and releases the lock when the run ends or is killed.

Every run is safe to repeat: the eval harness skips a trial that already has a graded `result.json`. To resume a stopped or partial run, start the same experiment again with the same command. Nothing needs to be cleaned up first. To stop a run, kill the `run.sh` process; the trap releases the lock, and the harness kills its own container.
