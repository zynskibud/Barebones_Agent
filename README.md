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

The baseline is `py.files-bash.local.python.qwen3-8b.no-think`.

Results go to `runs/<config id>/<task>/<trial>/`. Each trial folder holds `transcript.jsonl` and `result.json`.

## Layout

```
Barebones_Agent/
├── README.md
├── CLAUDE.md
├── .gitignore                    runs/ is ignored
├── docs/
│   ├── plan.html                 the plan page: diagram, configurations, evals, plan
│   └── harness-spec.md           the rules that every harness must follow
├── config/
│   ├── baseline.yaml             one configuration, for a chat
│   ├── grid.yaml                 the axes, for the evals
│   ├── system_prompt.txt         the system prompt, shared by every harness
│   ├── tools.json                the tool definitions and the tool sets
│   └── messages.json             the error and result strings
├── src/
│   ├── harness/                  the agent: one folder per language
│   │   ├── python/
│   │   │   ├── main.py           starts the agent: chat mode or task mode
│   │   │   ├── build.py          build_agent(): the composition root
│   │   │   ├── loop.py           the loop
│   │   │   ├── model.py          talks to Ollama (model seam)
│   │   │   ├── tools/            tools seam: files.py, bash.py
│   │   │   └── env/              environment seam: local.py, docker.py, cloud.py
│   │   ├── typescript/           same shape, later
│   │   └── go/                   same shape, later
│   └── evals/                    the eval harness, Python only
│       ├── run.py                grid → configurations → suites
│       ├── suite.py              one configuration: tasks × trials
│       ├── grade.py              runs the hidden tests
│       └── report.py             pass@1, pass@3, pass^3
├── tasks/                        codebase seam (data)
│   ├── python/task-01-cart-total/   task.yaml, repo/, solution/, hidden_tests/
│   ├── typescript/
│   └── rust/
└── runs/                         results, not in git
```

### Folder purposes

| Folder | Purpose |
|---|---|
| `Barebones_Agent/` | The repo root. |
| `docs/` | The plan page and the harness contract. |
| `config/` | The configuration choices, and the shared text that every harness loads: the system prompt, the tool definitions, and the error strings. The code reads them, and the code does not hold them. |
| `src/` | Code only. No tasks, config, or results. |
| `src/harness/` | The agent. One folder for each harness language. |
| `src/harness/python/` | The Python agent: entry point, composition root, loop, model client. |
| `src/harness/python/tools/` | The tools seam. One file for each tool group. |
| `src/harness/python/env/` | The environment seam. One file for each place where the tools act. |
| `src/harness/typescript/` | The TypeScript agent. Same shape as the Python agent. Not started. |
| `src/harness/go/` | The Go agent. Same shape as the Python agent. Not started. |
| `src/evals/` | The eval harness. It starts the agent as a separate program and grades the result. |
| `tasks/` | The codebase seam. Task data for each codebase language. |
| `tasks/python/` | Python tasks. |
| `tasks/python/task-01-cart-total/` | One task. It holds `task.yaml` and the three folders below. |
| `tasks/.../repo/` | The code that the agent starts with. |
| `tasks/.../solution/` | A correct fix. The agent never sees it. |
| `tasks/.../hidden_tests/` | The tests that grade the trial. The agent never sees them. |
| `tasks/typescript/` | TypeScript tasks. |
| `tasks/rust/` | Rust tasks. |
| `runs/` | Eval results, one folder for each configuration. Not in git. |

## How to run (planned)

The code is not written yet. These commands are the plan. They do not work today.

Get the model:

```
ollama pull qwen3:8b
ollama show qwen3:8b     # check the context length
ollama ps                # check the loaded model and its context
```

Chat with the agent in a folder:

```
python src/harness/python/main.py --config config/baseline.yaml --workdir <folder>
```

Run the evals:

```
python src/evals/run.py --stage 1     # pilot: baseline only
python src/evals/run.py --stage 2     # one axis at a time: 10 configurations
python src/evals/run.py               # full grid: 162 configurations
```

## How the evals work

- A **suite** is the fixed tasks, grader, limits, and prompt. It has 10 tasks for each codebase language.
- A **run** is one configuration against the suite.
- A **trial** is one attempt at one task. Each task gets 3 trials.
- For each trial, the eval harness copies `repo/` to a temp folder and runs the agent there. Then it copies `hidden_tests/` in and grades the result.
- The headline metric is pass@1. The report also gives pass^3, time per solved task, tokens, turns, and time.

The evals have three stages. Stage 1 is a pilot on the baseline. Stage 2 changes one axis at a time. Stage 3 is the full grid.

## Status

- Part 1: the repo structure. Done.
- Part 2: build every part in six subagent waves. The Plan tab in `docs/plan.html` lists the waves. Next.

Nothing runs yet.

## More

- `docs/plan.html` has the diagram, the configurations, the evals, and the plan.
- `docs/harness-spec.md` is the contract. It fixes the CLI flags, the loop, the transcript format, and the limits. It points to the shared data files in `config/` for the exact text.
