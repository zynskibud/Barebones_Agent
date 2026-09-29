# Harbor: Terminal-Bench 2.1 with the Python harness

Harbor (https://github.com/harbor-framework/harbor, docs at https://harborframework.com) runs benchmark tasks. It starts one container for each task, lets an agent act in it, and then runs the task's verifier. Our harness stays the harness. The only new parts are one env and one adapter.

- `src/harness/python/env/harbor.py`: `HarborEnv`, the `Env` interface on top of Harbor's environment object.
- `src/evals/harbor/agent.py`: `BarebonesAgent`, the class that Harbor loads as a custom agent.

Ollama stays on the host. The loop runs on the host. Only the tools act in Harbor's container.

## Install

Harbor 0.23.0 is in the project venv:

```
uv add harbor
```

## Harbor's agent API

A custom agent subclasses `harbor.agents.base.BaseAgent` and fills in these members:

- `name()` (static) and `version()`.
- `async setup(environment)`: install the agent in the container. Ours does nothing.
- `async run(instruction, environment, context)`: do the task. Harbor gives the task instruction, the environment, and an `AgentContext` for token counts and metadata.

The constructor gets `logs_dir`, the host folder `<trial folder>/agent/`. Harbor sets `session_id` to `<task>__<7 characters>__agent`. The task part has at most 32 characters.

## Harbor's environment API

`harbor.environments.base.BaseEnvironment`. All methods are async:

- `exec(command, cwd=None, env=None, timeout_sec=None, user=None)` returns `ExecResult(stdout, stderr, return_code)`. The Docker environment raises `RuntimeError("Command timed out ...")` at `timeout_sec`.
- `upload_file(source_path, target_path)`, `upload_dir`, `download_file`, `download_dir`.
- `task_env_config.workdir`: the task work folder, or `None`. If it is `None`, the adapter runs `pwd` to find it.

## How HarborEnv maps our Env

- `safe_path`: pure path logic on the container work root, as in the cloud env.
- `read`, `list`: one `exec` call each. A shell test gives the not-found, folder, and not-a-folder cases.
- `write`: `mkdir -p` through `exec`, then `upload_file` from a host temp file.
- `run`: `exec` in the work root with `timeout --signal KILL 30 bash -c <command>`, as in the docker env. Exit code 137 after the timeout gives `Timeout`.
- `start`, `stop`: nothing. Harbor owns the container.

The loop is sync. The adapter runs it in a worker thread. `HarborEnv` sends each coroutine to Harbor's event loop and waits for the result.

## Config

The adapter reads `config/baseline.yaml` and sets `env: harbor` and `codebase: terminal-bench-2-1`. Then it applies `HARBOR_SET`, in `key=value,key=value` form. Example: `HARBOR_SET=prompt=config/system_prompt_v2.txt,think=true`.

## Run a subset

Run from the repo root. `PYTHONPATH=.` makes the import path work.

```
caffeinate -i env PYTHONPATH=. HARBOR_SET=prompt=config/system_prompt_v2.txt \
  uv run harbor run \
  --dataset terminal-bench/terminal-bench-2-1 \
  --agent src.evals.harbor.agent:BarebonesAgent \
  --n-concurrent 1 \
  --jobs-dir runs/harbor-tb21 \
  --job-name tb21-subset \
  -i <task-name> -i <task-name> ...
```

- `-i` / `--include-task-name` selects a task. It takes glob patterns. Give it once for each task.
- `-l` / `--n-tasks` caps the number of tasks after the filters.
- `-n` / `--n-concurrent` sets how many tasks run at once. Keep it at 1.
- The Harbor Hub lists the dataset as `terminal-bench/terminal-bench-2-1`, with 89 tasks: https://hub.harborframework.com/datasets. `harbor dataset list` prints only that link.

## What a run writes

- `runs/harbor-tb21/tb21-subset/<task>__<id>/agent/transcript.jsonl` and `result.json`: ours, in the spec format. `task` is the Harbor task name. `trial` is null, because the folder is named `agent`. `passed` stays null.
- The rest of the trial folder, for example `verifier/` and the trial `result.json`: Harbor's, with the reward.

## Time caps

Three layers bound how long one task can take, real time included:

1. Harbor's own multipliers (`--environment-build-timeout-multiplier`,
   `--agent-timeout-multiplier`, `--verifier-timeout-multiplier`), on the `--dataset`
   values for the build, the agent, and the verifier. Harbor measures these in real
   time and kills the phase itself. See `experiments.yaml`, entry
   `harbor-terminal-bench-2.1-subset`, for the values chosen and the arithmetic.
2. The adapter's real-time cap, `HARBOR_WALL_SECONDS` (env var, default 600 seconds),
   in `src/evals/harbor/agent.py`. It measures the whole agent phase with `time.time()`,
   which counts a system sleep. If the loop thread is not done by the cap, the adapter
   stops waiting, sets a flag that stops the loop before its next model call, writes
   `result.json` itself with `stop_reason: "wall_clock"` and `wall_seconds` (the real
   elapsed time), and returns so Harbor proceeds to the verifier.
3. The loop's own awake budget, `max_seconds` in `config/baseline.yaml` (300 seconds by
   default). `src/harness/python/loop.py` measures this with `time.monotonic()`, which
   does not advance across a system sleep. This is why layer 2 exists: a laptop that
   sleeps during a run can make layer 3 alone let a task run for hours of real time.

Scoring rule: `src/evals/harbor/score.py` excludes a trial from the score if its agent
`stop_reason` is `wall_clock` or its agent `exit_code` is 139 (a crash, for example a
segfault under the qemu emulation that Terminal-Bench 2.1 tasks run under), and lists it
separately as "emulation: excluded". A trial with no `agent/result.json` at all (the
agent phase never finished setup) is excluded too, as "no agent run".

## Not known until a real run

- The exact dataset reference that `--dataset` accepts for Terminal-Bench 2.1.
- Whether every task image has bash and GNU `timeout`.
- The file owner after `upload_file`. It can be root and not the task user.
- Whether the verifier reward lands where the section above says.
- The time for image pulls and builds on this machine.
