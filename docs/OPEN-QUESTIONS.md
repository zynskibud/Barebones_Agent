# Open questions

Decisions that need the human. After each experiment, append the question, the default taken, and the effect of the default. Runs do not block on these.

| Date | Experiment | Question | Default taken | Effect of the default | Status |
|---|---|---|---|---|---|
| 2026-09-25 | Experiment 1 | The v2-think cell stopped at 26 of 30 on `local`. Keep the partial cell or finish it? | Keep the 26 local results as a partial cell and rerun the full cell in docker (`runs/exp1/v2-think-docker`). | The 2x2 has one cell from docker and three from local; the docker cell is the one used for later comparisons. | open |
| 2026-09-25 | Stage 2 | Run stage 2 with prompt v1 (the frozen spec text) or prompt v2? | v2, via `--set prompt=config/system_prompt_v2.txt`, into `runs/stage2-v2`. | Axis effects are measured against a 0.37 baseline instead of 0.07; v1 stays as the pilot reference only. | open |
| 2026-09-25 | Thinking mode | 14 of 30 thinking-on trials hit the 300 s limit. Raise `max_seconds` for thinking configurations? | Keep 300 s for every configuration, so the cells stay comparable; revisit after stage 2. | Thinking-on scores are lower than they would be with a longer limit; time per trial stays bounded. | open |
| 2026-09-25 | Grid | `local` with a bash tool set is blocked (36 configurations). Drop `local` from the grid, or keep it for the `files` tool set only? | Keep `local` for `files` only; the blocked 36 stay out of every count in `experiments.yaml`. | The environment axis is measured on 3 values for `files` and on 2 for `bash` and `files-bash`. | open |
| 2026-09-25 | Cost | E2B spend per experiment is under $1 today. Approve E2B use up to $5 without asking? | Yes, per the protocol's $5 rule. | Cloud configurations run in stage 2 and the grid without a pause. | open |
