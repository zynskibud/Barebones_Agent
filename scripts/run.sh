#!/usr/bin/env bash
# Run one experiment from experiments.yaml, under the coordinator's heavy lock.
#
# Usage: scripts/run.sh [--force] [--dry-run] <experiment-id>
#
# Steps: look up the experiment, refuse unless its status is "ready" (unless
# --force), run preflight and stop on failure, take the heavy lock, run the
# command, always release the lock, then print the report table.
#
# --dry-run does everything except the command: it still takes and releases
# the lock and prints what it would run. Use it to check the lock logic
# without starting Ollama, Docker, or E2B work.
#
# Safe to re-run: the eval harness skips a trial that already has a graded
# result.json, so running the same experiment again continues it.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AI_ENGINEERING_ROOT="$(cd "$REPO_ROOT/.." && pwd)"
LOCK_DIR="$AI_ENGINEERING_ROOT/.coord/heavy.lock"
LOCK_OWNER_FILE="$LOCK_DIR/owner"
EXPERIMENTS_FILE="$REPO_ROOT/experiments.yaml"

FORCE=0
DRY_RUN=0
EXPERIMENT_ID=""
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help)
      echo "usage: scripts/run.sh [--force] [--dry-run] <experiment-id>"
      exit 0
      ;;
    *) EXPERIMENT_ID="$arg" ;;
  esac
done

if [ -z "$EXPERIMENT_ID" ]; then
  echo "usage: scripts/run.sh [--force] [--dry-run] <experiment-id>" >&2
  exit 2
fi

# Read the experiment's status, command, and results folder from the queue.
lookup="$(cd "$REPO_ROOT" && uv run python -c "
import sys, yaml
data = yaml.safe_load(open('experiments.yaml'))
matches = [e for e in data if e.get('id') == sys.argv[1]]
if not matches:
    sys.exit('no experiment named ' + sys.argv[1] + ' in experiments.yaml')
e = matches[0]
print(e.get('status') or '')
print(e.get('command') or '')
print(e.get('results') or '')
" "$EXPERIMENT_ID")"
lookup_status=$?
if [ $lookup_status -ne 0 ]; then
  echo "$lookup" >&2
  exit 2
fi

STATUS="$(printf '%s\n' "$lookup" | sed -n '1p')"
COMMAND="$(printf '%s\n' "$lookup" | sed -n '2p')"
RESULTS="$(printf '%s\n' "$lookup" | sed -n '3p')"

if [ -z "$COMMAND" ]; then
  echo "refusing: $EXPERIMENT_ID has no command in experiments.yaml yet" >&2
  exit 2
fi

if [ "$STATUS" != "ready" ] && [ "$FORCE" -ne 1 ]; then
  echo "refusing: $EXPERIMENT_ID status is '$STATUS', not ready. Use --force to run it anyway." >&2
  exit 2
fi

echo "experiment: $EXPERIMENT_ID (status: $STATUS)"
echo "command: $COMMAND"

# Preflight. Stop here on a hard failure; do not touch the lock.
if ! "$REPO_ROOT/scripts/preflight.sh"; then
  echo "refusing: preflight failed" >&2
  exit 1
fi

# Acquire the coordinator's heavy lock, exactly as .coord/PROTOCOL.md says.
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "heavy lock is held. Owner:" >&2
  cat "$LOCK_OWNER_FILE" >&2 2>/dev/null
  exit 3
fi
echo "barebones-agent $EXPERIMENT_ID $(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$LOCK_OWNER_FILE"

release_lock() {
  rm -rf "$LOCK_DIR"
}
trap release_lock EXIT INT TERM

RESULTS_DIR="$REPO_ROOT/${RESULTS:-runs/$EXPERIMENT_ID}"
mkdir -p "$RESULTS_DIR"
LOG="$RESULTS_DIR/run.log"

if [ "$DRY_RUN" -eq 1 ]; then
  echo "[dry run] lock acquired: $LOCK_DIR"
  echo "[dry run] would append to $LOG and run: $COMMAND"
  echo "[dry run] releasing the lock now"
  exit 0
fi

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) start $EXPERIMENT_ID: $COMMAND" >> "$LOG"
( cd "$REPO_ROOT" && eval "$COMMAND" )
COMMAND_EXIT=$?
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) end $EXPERIMENT_ID exit=$COMMAND_EXIT" >> "$LOG"

echo
echo "report:"
(cd "$REPO_ROOT" && uv run python src/evals/report.py --runs "$RESULTS_DIR")

exit "$COMMAND_EXIT"
