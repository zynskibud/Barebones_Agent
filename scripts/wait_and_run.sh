#!/bin/bash
# Wait until no coordinator lock is held, then run the given experiments one
# after another through scripts/run.sh. Polls every 5 minutes. Meant to be
# started detached: nohup scripts/wait_and_run.sh id1 id2 ... > runs/waiter.log 2>&1 &
set -u
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COORD="$(cd "$REPO_ROOT/.." && pwd)/.coord"
cd "$REPO_ROOT"
for id in "$@"; do
  while [ -d "$COORD/gpu.lock" ] || [ -d "$COORD/heavy.lock" ] || [ -d "$COORD/timing.lock" ]; do
    echo "$(date '+%F %T') waiting: locks held: $(ls "$COORD" | grep -E 'lock$' | tr '\n' ' ')"
    sleep 300
  done
  folder="$(uv run python -c "import sys,yaml; d=yaml.safe_load(open('experiments.yaml')); print([x for x in d if x['id']==sys.argv[1]][0]['results'])" "$id")"
  mkdir -p "$folder"
  echo "$(date '+%F %T') starting $id -> $folder"
  scripts/run.sh "$id" > "$folder/console.log" 2>&1
  rc=$?
  echo "$(date '+%F %T') $id ended with exit $rc"
  if [ "$rc" -eq 3 ]; then
    echo "$(date '+%F %T') lock was taken first; retrying $id after 5 minutes"
    sleep 300
    set -- "$id" "$@"   # put the id back at the front and try again
  fi
done
echo "$(date '+%F %T') all done"
