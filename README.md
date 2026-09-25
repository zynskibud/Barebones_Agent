# Barebones Agent

Barebones Agent builds an agent harness from scratch. It evaluates which models and agent configurations work for different kinds of tasks. At this time, the project tests only software engineering (SWE) tasks.

## Configurations

The project has six axes:

| Axis | Values | Meaning |
|---|---|---|
| harness | `py`, `ts`, `go` | The language of the agent loop |
| tools | `files`, `bash`, `files-bash` | The tool set that the model sees |
| env | `local`, `docker`, `cloud` | Where the tools act |
| codebase | `python`, `typescript`, `rust` | The language of the task repos |
| model | `qwen3:8b` | The Ollama tag (one value) |
| think | `false`, `true` | Qwen3 thinking mode |

3 × 3 × 3 × 3 × 1 × 2 = **162 configurations**.

The tools are `read_file`, `list_files`, `edit_file`, and `bash`:

- `files` gives `read_file`, `list_files`, `edit_file`.
- `bash` gives `bash` only.
- `files-bash` gives all four.

### Configuration ID

```
<harness>.<tools>.<env>.<codebase>.<model-id>.<think-id>
```

- `model-id` is the Ollama tag with `:` changed to `-`. For example, `qwen3-8b`.
- `think-id` is `think` or `no-think`.

The baseline is `py.files-bash.docker.python.qwen3-8b.no-think`. The pilot and Experiment 1 ran on `local`, before the baseline moved to `docker` on 2026-09-25.

Results go to `runs/<config id>/<task>/<trial>/`. Each trial folder holds `transcript.jsonl` and `result.json`.

## Layout

```
Barebones_Agent/
├── README.md
├── CLAUDE.md
├── .gitignore                    runs/ is ignored
├── docs/
│   ├── plan.html                 the plan page: diagram, configurations, evals, plan
│   ├── harness-spec.md           the rules that every harness must follow
│   └── pilot.md                  the stage 1 pilot: numbers, failure groups, fixes
├── config/
│   ├── baseline.yaml             one configuration, for a chat
│   ├── grid.yaml                 the axes, for the evals
│   ├── system_prompt.txt         the system prompt, shared by every harness
│   ├── tools.json                the tool definitions and the tool sets
│   └── messages.json             the error and result strings
├── docker/
│   ├── Dockerfile                the image for env: docker, with the three toolchains
│   └── README.md                 how to build it, and what it holds
├── cloud/
│   ├── build_template.py         builds the E2B template for env: cloud
│   └── README.md                 how to build it, and what it holds
├── src/
│   ├── harness/                  the agent: one folder per language
│   │   ├── python/
│   │   │   ├── main.py           starts the agent: chat mode or task mode
│   │   │   ├── build.py          build_agent(): the composition root
│   │   │   ├── loop.py           the loop
│   │   │   ├── model.py          talks to Ollama (model seam)
│   │   │   ├── tools/            tools seam: registry.py, files.py, bash.py
│   │   │   └── env/              environment seam: base.py, local.py, docker.py, cloud.py
│   │   ├── typescript/           the TypeScript agent, same shape: main.ts, build.ts, loop.ts, model.ts, tools/, env/
│   │   └── go/                   the Go agent, same shape: main.go, build.go, loop.go, model.go, tools/, env/
│   └── evals/                    the eval harness, Python only
│       ├── run.py                grid → configurations → suites
│       ├── suite.py              one configuration: tasks × trials
│       ├── grade.py              runs the hidden tests
│       ├── report.py             pass@1, pass@k, pass^k
│       └── tests/                tests for the eval harness
├── tasks/                        codebase seam (data)
│   ├── python/                   10 tasks, task-01-cart-total to task-10-slug-rename
│   │   └── task-NN-<slug>/       task.yaml, repo/, solution/, hidden_tests/
│   ├── typescript/               the same 10 tasks in TypeScript (node --test)
│   └── rust/                     the same 10 tasks in Rust (cargo test)
├── go.work                       makes the Go module visible from the repo root
├── bin/                          the built Go harness, not in git
└── runs/                         results, not in git
```

### Folder purposes

| Folder | Purpose |
|---|---|
| `Barebones_Agent/` | The repo root. |
| `docs/` | The plan page, the harness contract, and the pilot report. |
| `docker/` | The Dockerfile for the `docker` env image `barebones-task`: Python 3.12 with pytest, Node 24, Rust 1.98. |
| `cloud/` | The build script for the E2B template `barebones-agent` for the `cloud` env. The same toolchains. |
| `config/` | The configuration choices, and the shared text that every harness loads: the system prompt, the tool definitions, and the error strings. The code reads them, and the code does not hold them. |
| `src/` | Code only. No tasks, config, or results. |
| `src/harness/` | The agent. One folder for each harness language. |
| `src/harness/python/` | The Python agent: entry point, composition root, loop, model client. |
| `src/harness/python/tools/` | The tools seam. One file for each tool group. |
| `src/harness/python/env/` | The environment seam. One file for each place where the tools act. |
| `src/harness/typescript/` | The TypeScript agent. Same shape as the Python agent. Node 24 runs the `.ts` files directly. The `e2b` package, for the `cloud` env, is its only dependency. |
| `src/harness/go/` | The Go agent. Same shape as the Python agent. Standard library only, including the E2B calls for the `cloud` env. |
| `bin/` | The built Go harness, `barebones-go`. The eval harness builds it on first use. Not in git. |
| `go.work` | The Go workspace file. It makes the Go module under `src/harness/go/` visible from the repo root. |
| `src/evals/` | The eval harness. It starts the agent as a separate program and grades the result. |
| `tasks/` | The codebase seam. Task data for each codebase language. |
| `tasks/python/` | The 10 Python tasks: 4 bug fixes, 4 features, 2 refactors. |
| `tasks/python/task-NN-<slug>/` | One task. It holds `task.yaml` and the three folders below. |
| `tasks/.../repo/` | The code that the agent starts with. |
| `tasks/.../solution/` | A correct fix. The agent never sees it. |
| `tasks/.../hidden_tests/` | The tests that grade the trial. The agent never sees them. |
| `tasks/typescript/` | The same 10 tasks in TypeScript. Node 24 runs the `.ts` tests with `node --test`. |
| `tasks/rust/` | The same 10 tasks in Rust. Each task is a cargo package. The tests run with `cargo test`. |
| `runs/` | Eval results, one folder for each configuration. Not in git. |

## How to run

The three harnesses and the eval harness run on the three envs and the three codebases.

### Prerequisites

- Ollama with the model: `ollama pull qwen3:8b`.
- uv. It gives Python 3.12, `pytest`, `pyyaml`, and `e2b`. Run `uv sync` once.
- For `env: docker`: Docker Desktop, and the image. Build it once: `docker build -t barebones-task docker/`.
- For `env: cloud`: an E2B account, the key in `.env` at the repo root as `E2B_API_KEY=...`, and the template. Build it once: `uv run python cloud/build_template.py`.
- For the TypeScript tasks on the host and for the `ts` harness: Node 24 through fnm. The eval harness puts `~/.local/share/fnm/node-versions/v24*/installation/bin` in front of PATH when it exists. The fnm default can stay at another version.
- For the `ts` harness on `env: cloud`: the `e2b` package. Run `npm install --prefix src/harness/typescript` once.
- For the `go` harness: Go 1.27. The Go binary builds itself into `bin/` on first use, and again when a source file is newer than the binary.
- For the Rust tasks on the host: cargo in `~/.cargo/bin`. The eval harness puts it on PATH when it exists.

The `docker` and `cloud` envs move only the `bash` tool. The eval harness grades on the host in every env, so the host needs the toolchain of the codebase.

### Machine

Run evals on power with the lid open. System sleep stretches the timers and kills the sandboxes: the Node clock counts the time in sleep, and the E2B sandbox timeout is real time.

Check the model:

```
ollama show qwen3:8b     # check the context length
ollama ps                # check the loaded model and its context
```

Chat with the agent in a folder:

```
uv run python src/harness/python/main.py --config config/baseline.yaml --workdir <folder>
```

Run one task without a chat (this is what the eval harness does):

```
uv run python src/harness/python/main.py --config config/baseline.yaml --workdir <folder> \
  --mode task --prompt-file <file> --transcript <path>.jsonl --result <path>.json
```

The same flags start the other two harnesses: `node src/harness/typescript/main.ts` and `bin/barebones-go`.

Check every task (each must fail on its start code and pass on its solution):

```
uv run python src/evals/run.py --validate-tasks
```

Run the evals:

```
uv run python src/evals/run.py --stage 1     # pilot: baseline only
uv run python src/evals/run.py --stage 2     # one axis at a time: 10 configurations
uv run python src/evals/run.py               # full grid: 162 configurations
uv run python src/evals/run.py --dry-run     # print the configuration IDs and exit
uv run python src/evals/report.py            # the table: pass@1, pass^k, time per solved task
```

Run exact configurations. Repeat `--config` or separate the IDs with commas. `--runs` puts the results in another folder, so a check does not touch the eval results:

```
uv run python src/evals/run.py --config py.files-bash.docker.rust.qwen3-8b.no-think \
  --trials 1 --tasks task-01-cart-total --runs runs/smoke
uv run python src/evals/report.py --runs runs/smoke
```

Experiment 1 has four cells: prompt v1 or v2, thinking off or on. `--set prompt=config/system_prompt_v2.txt` writes the `prompt` key into every config file of the run. The configuration ID does not name the prompt, so each cell goes into its own `--runs` folder:

```
caffeinate -i uv run python src/evals/run.py --runs runs/exp1/v1-nothink --config py.files-bash.local.python.qwen3-8b.no-think
caffeinate -i uv run python src/evals/run.py --runs runs/exp1/v1-think   --config py.files-bash.local.python.qwen3-8b.think
caffeinate -i uv run python src/evals/run.py --runs runs/exp1/v2-nothink --config py.files-bash.local.python.qwen3-8b.no-think --set prompt=config/system_prompt_v2.txt
caffeinate -i uv run python src/evals/run.py --runs runs/exp1/v2-think   --config py.files-bash.local.python.qwen3-8b.think    --set prompt=config/system_prompt_v2.txt
uv run python src/evals/report.py --runs runs/exp1/v1-nothink
uv run python src/evals/report.py --runs runs/exp1/v1-think
uv run python src/evals/report.py --runs runs/exp1/v2-nothink
uv run python src/evals/report.py --runs runs/exp1/v2-think
```

- Experiment 1 is complete: pass@1 v1/off 0.067, v2/off 0.367, v1/on 0.433, v2/on 0.333 (docker). Working setting: prompt v2, thinking off. Next: stage 2 on the coordinator's GO. See `docs/pilot.md`.

## How the evals work

- A **suite** is the fixed tasks, grader, limits, and prompt. It has 10 tasks for each codebase language.
- A **run** is one configuration against the suite.
- A **trial** is one attempt at one task. Each task gets 3 trials. A trial has 20 turns and 300 seconds (`max_turns` and `max_seconds`).
- For each trial, the eval harness copies `repo/` to a temp folder and runs the agent there. Then it copies `hidden_tests/` in and grades the result.
- The headline metric is pass@1. The report also gives pass^3, time per solved task, tokens, turns, and time.

The evals have three stages. Stage 1 is a pilot on the baseline. Stage 2 changes one axis at a time. Stage 3 is the full grid.

## Status

- Part 1: the repo structure. Done.
- Part 2: build every part in six subagent waves. The Plan tab in `docs/plan.html` lists the waves. Waves 0 to 6 are done.
  - Waves 0 to 2: the Python harness, the 10 Python tasks, the eval harness, and the pilot. The pilot ran stage 1 on the baseline: pass@1 0.10 (3 of 30 trials) at 229 seconds per trial. `docs/pilot.md` has the numbers and the failure groups.
  - Wave 3: the `docker` and `cloud` envs, and the TypeScript and Rust tasks.
  - Wave 4: integration. The Python harness ran a smoke run over the 3 envs × 3 codebases. The table is in `docs/pilot.md`, section "After the pilot". The spec is frozen as version 1.
  - Wave 5: the TypeScript and Go harnesses. Both match the Python harness byte for byte on the tool JSON, the prompt, and the request bodies.
  - Wave 6: integration. Harness check: the baseline with each of the three harnesses on tasks 01 and 07, 6 of 6 trials valid, the same first-call prompt tokens (527) for all three. Stage 2 smoke: the 10 stage 2 configurations on tasks 01 and 07, 20 of 20 trials valid, 10 passed, 0 infra errors, no leftover container or sandbox. Both tables are in `docs/pilot.md`, section "After wave 6". The spec gained a clarifications section (15), still version 1.
  - Experiment 1 (prompt × thinking, 4 × 30 trials) ran on `local`. Three cells are done: v1-nothink, v2-nothink, v1-think. The fourth cell, v2-think, stopped at 26 of 30 trials and needs a full rerun. See `docs/pilot.md`, section "Experiment 1 results".
  - Next: the v2-think rerun in `docker` (`runs/exp1/v2-think-docker`), then the stage 2 measurement. See `experiments.yaml`.
- Two decisions after the pilot. Each one is reversible with one line.
  - The limits are 20 turns and 300 seconds. The pilot used 40 and 600. No passing pilot trial used more than 4 turns, and the failed loops burned 40 turns and up to 600 seconds. To go back, set `max_turns: 40` and `max_seconds: 600` in `config/baseline.yaml` and in the `limits` of every `task.yaml`.
  - Every Python task has an empty `conftest.py` in `repo/` and `solution/`, so a bare `pytest` finds the module under test, as `npm test` and `cargo test` find theirs. To go back, delete these 20 files.
- The baseline env is now `docker` (2026-09-25). `local` with a bash tool set is blocked in `run.py` unless `--allow-local-bash` is passed. See "Running experiments" below.

## Running experiments

Every model run on this machine goes through the run contract, not a bare `run.py` call:

- `experiments.yaml` is the queue: one entry per experiment, with its status, its exact command, and its result folder.
- `scripts/preflight.sh` checks the machine (Ollama, Docker, disk, the coordinator lock) before a run.
- `scripts/run.sh <experiment-id>` runs preflight, takes the coordinator lock, runs the command, and always releases the lock.
- `scripts/status.sh` shows how every experiment is doing.
- `docs/handoff.md` is the state of the project for a session that has not seen it before. Read it first.

Isolation rule: the evaluated agent's `bash` tool is not fenced on `env: local`. Runs use `env: docker` or `env: cloud`. `env: local` is allowed only with the `files` tool set, because `safe_path` fences only the file tools. `local` with `bash` or `files-bash` is blocked in `run.py` unless the owner passes `--allow-local-bash`.

## More

- `docs/plan.html` has the diagram, the configurations, the evals, and the plan.
- `docs/harness-spec.md` is the contract. It fixes the CLI flags, the loop, the transcript format, and the limits. It points to the shared data files in `config/` for the exact text.
