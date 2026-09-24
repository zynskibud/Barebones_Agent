# Barebones Agent: rules for AI assistants

Barebones Agent is one agent loop, a few tools, and one local model (Qwen3 8B through Ollama). It is tested across 162 configurations.

This is a hand-built learning project. The owner writes every part by hand.

- Do not use agent frameworks.
- Do not use SDK tool runners.
- Write the loop by hand.

## Structure rules

1. `src/` holds only code. Tasks, config, and results are data. All three harness languages read the same data. The system prompt, the tool definitions, and the error strings are in `config/system_prompt.txt`, `config/tools.json`, and `config/messages.json`. Never copy their text into code.
2. The eval harness never imports the agent. It starts the agent as a separate program. This process boundary makes the harness-language axis possible.
3. `docs/harness-spec.md` is the contract. It fixes the CLI flags, the system prompt, the tool descriptions, the transcript format, and the limits. Every harness follows it word for word.
4. Each seam is a folder. A new part is a new file in the correct folder. Nothing else changes.
5. Every task has the same four parts: `task.yaml`, `repo/`, `solution/`, `hidden_tests/`. `task.yaml` holds the facts that differ between languages, for example the test command (`pytest`, `node --test`, or `cargo test`).

## Seams and the composition root

A seam is the place in the code where one part can be swapped for another.

- model: value seam. One file in each harness (`model.py`, `model.ts`, `model.go`).
- tools: behavior seam. The `tools/` folder in each harness.
- env: behavior seam. The `env/` folder in each harness.
- tasks: data seam. `tasks/<codebase>/`, shared by every harness.
- harness per language: the whole program. `src/harness/python/`, `src/harness/typescript/`, and `src/harness/go/` have the same shape. The eval harness picks the language by starting a different program.

The choice is made in `config/baseline.yaml`. Only the composition root reads it: `build.py`, `build.ts`, or `build.go`. Nothing below the composition root checks the config.

## Configuration IDs and results

The ID is `<harness>.<tools>.<env>.<codebase>.<model-id>.<think-id>`.

- `model-id` is the Ollama tag with `:` changed to `-`, for example `qwen3-8b`.
- `think-id` is `think` or `no-think`.
- The baseline is `py.files-bash.local.python.qwen3-8b.no-think`.

Results go to `runs/<config id>/<task>/<trial>/`. Each trial folder holds `transcript.jsonl` and `result.json`.

## Tasks and hidden tests

- Each task lives at `tasks/<codebase>/<task-id>/`.
- `hidden_tests/` and `solution/` never enter the agent's working folder while the agent works.
- The eval harness copies `repo/` to a temp folder and runs the agent. Then it copies `hidden_tests/` in and grades.
- The file tools enforce the working-folder limit with a `safe_path` check in `env/`.
- On the laptop, `bash` cannot be limited that way. Search the transcripts for reads of `hidden_tests` or `solution`.
- In `env: docker`, `bash` runs in a container and sees only `/work`, the working folder. The file tools run on the host.
- In `env: cloud`, `bash` runs in an E2B sandbox that holds only a copy of the working folder. The copy comes back to the host when the harness stops.

## Rules

- Every harness must match `docs/harness-spec.md` word for word. If you change the spec, change it in the spec first.
- Never commit `runs/`. Commit only summary reports.
- Run model evals on power with the lid open. System sleep stretches the timers and kills the sandboxes.
- The eval harness is Python. The agent harnesses come in three languages. Do not share code between `src/evals` and `src/harness`.
- Do not add dependencies or abstractions for parts that do not exist yet.
- If the axes, counts, or plan change, update `docs/plan.html` in the same change.
- Do not write project codes (for example H1 or E2) in any file.
