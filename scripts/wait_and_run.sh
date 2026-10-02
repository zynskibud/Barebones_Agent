#!/bin/bash
# Wait until no coordinator lock is held, then run the given experiments one
# after another through scripts/run.sh. Polls every 5 minutes. Meant to be
# started detached: nohup scripts/wait_and_run.sh id1 id2 ... > runs/waiter.log 2>&1 &
set -u
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COORD="$(cd "$REPO_ROOT/.." && pwd)/.coord"
cd "$REPO_ROOT"
for id in "$@"; do
  # Wait while a lock is held, while gpu.next reserves the GPU for another job,
  # or while free disk is under the preflight floor (15 GB).
  while true; do
    reason=""
    held="$(ls "$COORD" | grep -E 'lock$' | tr '\n' ' ')"
    [ -n "$held" ] && reason="locks held: $held"
    if [ -f "$COORD/gpu.next" ] && ! grep -q "barebones $id" "$COORD/gpu.next"; then
      reason="$reason gpu.next reserved for: $(cat "$COORD/gpu.next")"
    fi
    free_gb=$(df -g / | awk 'NR==2 {print $4}')
    [ "$free_gb" -lt 15 ] && reason="$reason disk free ${free_gb} GB (needs 15)"
    [ -z "$reason" ] && break
    echo "$(date '+%F %T') waiting: $reason"
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
