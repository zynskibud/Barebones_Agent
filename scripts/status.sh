#!/usr/bin/env bash
# Print the state of every experiment in experiments.yaml, plus the
# coordinator lock and any running processes.
#
# For each entry with a results folder: the id, the status, trials done
# versus expected, and, if the entry is done, the report.py line for it.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AI_ENGINEERING_ROOT="$(cd "$REPO_ROOT/.." && pwd)"
LOCK_DIR="$AI_ENGINEERING_ROOT/.coord/heavy.lock"

echo "Experiment status, $(date)"
echo

cd "$REPO_ROOT" && uv run python -c "
import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path('.').resolve()
sys.path.insert(0, str(REPO_ROOT / 'src' / 'evals'))
import report  # noqa: E402

data = yaml.safe_load(open(REPO_ROOT / 'experiments.yaml', encoding='utf-8'))


def count_done(folder: Path) -> int:
    '''Count result.json files with a graded (non-null) passed value, at any depth.'''
    n = 0
    for path in folder.glob('**/trial-*/result.json'):
        try:
            record = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if isinstance(record, dict) and isinstance(record.get('passed'), bool):
            n += 1
    return n


def report_table(folder: Path) -> str | None:
    '''Return the report.py table for this folder, or None if it has no graded trials.

    A results folder normally holds one or more config-id folders, which is what
    report.load_results expects. The pilot folder is the config-id folder itself,
    one level short, so fall back to the parent and keep only this folder's row.
    '''
    results, _ = report.load_results(folder)
    if not results:
        parent_results, _ = report.load_results(folder.parent)
        results = [r for r in parent_results if r['_config'] == folder.name]
    if not results:
        return None
    rows = report.build_report(results)
    return report.format_table(rows)


for entry in data:
    folder_name = entry.get('results')
    if not folder_name:
        continue
    folder = REPO_ROOT / folder_name
    expected = entry.get('trials')
    done = count_done(folder) if folder.is_dir() else 0
    trial_text = f'{done}/{expected}' if expected is not None else str(done)
    print(f\"{entry['id']:<30} status={entry['status']:<10} trials={trial_text:<10} folder={folder_name}\")
    if entry.get('status') == 'done' or done:
        table = report_table(folder)
        if table:
            for line in table.splitlines():
                print('    ' + line)
        else:
            print('    no graded trials yet')
"

echo
echo "Coordinator lock:"
if [ -d "$LOCK_DIR" ]; then
  echo "  HELD by: $(cat "$LOCK_DIR/owner" 2>/dev/null || echo "(no owner file)")"
else
  echo "  free"
fi

echo
echo "Running barebones- containers:"
docker ps --filter 'name=barebones-' --format '  {{.Names}}' 2>/dev/null | sed '/^$/d' || true
if [ -z "$(docker ps --filter 'name=barebones-' --format '{{.Names}}' 2>/dev/null)" ]; then
  echo "  none"
fi

echo
echo "Running src/evals/run.py processes:"
running="$(pgrep -fl "src/evals/run.py" 2>/dev/null)"
if [ -n "$running" ]; then
  printf '%s\n' "$running" | sed 's/^/  /'
else
  echo "  none"
fi
