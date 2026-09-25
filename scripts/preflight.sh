#!/usr/bin/env bash
# Preflight checks for a model run on this machine.
#
# Prints one line per check. Exits 1 only on a hard failure: disk free under
# 15 GB. Every other check can print a warning and still let the run start,
# because a human decides what to do about a warning, not this script.
#
# This script never starts or stops Ollama, Docker, or a container. It only
# looks.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AI_ENGINEERING_ROOT="$(cd "$REPO_ROOT/.." && pwd)"
LOCK_DIR="$AI_ENGINEERING_ROOT/.coord/heavy.lock"
DISK_FAIL_GB=15
LOAD_WARN=2
HARD_FAIL=0

ok()   { printf 'OK    %s\n' "$1"; }
warn() { printf 'WARN  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; HARD_FAIL=1; }
info() { printf 'INFO  %s\n' "$1"; }

echo "Preflight for Barebones Agent, $(date)"
echo "Repo: $REPO_ROOT"
echo

# Lid state. A closed lid can put the machine to sleep, which stretches
# every timer and can kill a running sandbox.
clamshell="$(ioreg -r -k AppleClamshellState -d 4 2>/dev/null | grep -o '"AppleClamshellState" = [A-Za-z]*' | awk '{print $NF}')"
case "$clamshell" in
  No)  ok "lid open" ;;
  Yes) warn "lid closed" ;;
  *)   warn "lid state unknown" ;;
esac

# Power source. Model runs are long; do not run them on battery alone.
if pmset -g batt 2>/dev/null | head -1 | grep -q "AC Power"; then
  ok "on AC power"
else
  warn "not on AC power"
fi

# Ollama daemon and the model.
tags_json="$(curl -s --max-time 2 http://localhost:11434/api/tags 2>/dev/null)"
if [ -n "$tags_json" ]; then
  ok "Ollama daemon up"
  if printf '%s' "$tags_json" | grep -q '"qwen3:8b"'; then
    ok "qwen3:8b present"
  else
    warn "qwen3:8b not found in Ollama"
  fi
else
  warn "Ollama daemon not reachable on localhost:11434"
fi

# What Ollama has loaded right now.
echo
echo "ollama ps:"
ollama ps 2>&1 | sed 's/^/  /'
echo

# Docker daemon and the task image.
if docker info >/dev/null 2>&1; then
  ok "Docker daemon up"
  if docker image inspect barebones-task >/dev/null 2>&1; then
    ok "barebones-task image present"
  else
    warn "barebones-task image not built (docker build -t barebones-task docker/)"
  fi
else
  warn "Docker daemon not reachable"
fi

# E2B key. Never print the key itself.
if [ -n "${E2B_API_KEY:-}" ]; then
  ok "E2B_API_KEY present (environment)"
elif [ -f "$REPO_ROOT/.env" ] && grep -q '^E2B_API_KEY=' "$REPO_ROOT/.env" 2>/dev/null; then
  ok "E2B_API_KEY present (.env)"
else
  warn "E2B_API_KEY missing"
fi

# Toolchains the harnesses and the grader need.
if [ -d "$REPO_ROOT/.venv" ]; then
  ok ".venv present"
else
  warn ".venv missing (run: uv sync)"
fi

if compgen -G "$HOME/.local/share/fnm/node-versions/v24*/installation/bin" >/dev/null 2>&1; then
  ok "Node 24 on the fnm path"
else
  warn "Node 24 not found under ~/.local/share/fnm/node-versions/"
fi

if [ -x "$HOME/.cargo/bin/cargo" ] || command -v cargo >/dev/null 2>&1; then
  ok "cargo present"
else
  warn "cargo not found"
fi

# Disk space. This is a hard failure: the protocol stops the whole machine
# at 15 GB free, not just this project.
disk_avail_gb="$(df -g / 2>/dev/null | awk 'NR==2{print $4}')"
if [ -n "$disk_avail_gb" ] && [ "$disk_avail_gb" -lt "$DISK_FAIL_GB" ]; then
  fail "disk free ${disk_avail_gb} GB, under the ${DISK_FAIL_GB} GB floor"
else
  ok "disk free ${disk_avail_gb:-unknown} GB"
fi

# Load average. A high load slows every model call; it is a warning, not a
# reason to stop.
load1="$(uptime | sed -E 's/.*load averages?: *//' | awk '{print $1}')"
if [ -n "$load1" ] && awk -v l="$load1" -v w="$LOAD_WARN" 'BEGIN{exit !(l>w)}'; then
  warn "load average ${load1} (over ${LOAD_WARN})"
else
  ok "load average ${load1:-unknown}"
fi

# The coordinator's heavy-job lock.
if [ -d "$LOCK_DIR" ]; then
  owner="$(cat "$LOCK_DIR/owner" 2>/dev/null || echo "(no owner file)")"
  info "coordinator lock: HELD by: $owner"
else
  info "coordinator lock: free"
fi

# Anything already running that a new run should know about.
running_containers="$(docker ps --filter 'name=barebones-' --format '{{.Names}}' 2>/dev/null)"
if [ -n "$running_containers" ]; then
  warn "running barebones- containers: $(printf '%s' "$running_containers" | tr '\n' ' ')"
else
  ok "no running barebones- containers"
fi

running_runpy="$(pgrep -fl "src/evals/run.py" 2>/dev/null)"
if [ -n "$running_runpy" ]; then
  warn "src/evals/run.py already running: $(printf '%s' "$running_runpy" | tr '\n' '; ')"
else
  ok "no running src/evals/run.py process"
fi

# E2B sandboxes. This calls the E2B API, so it can fail for reasons that
# have nothing to do with this machine; print "unknown" rather than fail.
e2b_count="unknown"
if [ -n "${E2B_API_KEY:-}" ] || { [ -f "$REPO_ROOT/.env" ] && grep -q '^E2B_API_KEY=' "$REPO_ROOT/.env" 2>/dev/null; }; then
  e2b_count="$(cd "$REPO_ROOT" && env $(grep -h '^E2B_API_KEY=' .env 2>/dev/null) uv run python -c '
from e2b import Sandbox
try:
    print(len(Sandbox.list().next_items()))
except Exception:
    print("unknown")
' 2>/dev/null)"
  [ -z "$e2b_count" ] && e2b_count="unknown"
fi
info "E2B running sandboxes: $e2b_count"

echo
if [ "$HARD_FAIL" -ne 0 ]; then
  echo "Preflight FAILED. Fix the hard failure above before a run."
  exit 1
fi
echo "Preflight OK (warnings, if any, are above)."
exit 0
