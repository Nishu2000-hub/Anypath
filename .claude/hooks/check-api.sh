#!/usr/bin/env bash
# PostToolUse: after an edit to a Python/config file under services/api,
# run mypy and pytest there. On failure, exit 2 so the output is fed back
# to Claude to fix.
set -uo pipefail

file=$(jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')
root="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
api="$root/services/api"

case "$file" in
  "$api"/*.py|"$api"/*.toml|"$api"/*.cfg|"$api"/*.ini) ;;
  *) exit 0 ;;
esac
case "$file" in "$api"/.venv/*) exit 0 ;; esac

py="$api/.venv/bin/python"
[ -x "$py" ] || py=python3
cd "$api" || exit 0

out=$("$py" -m mypy solver tests 2>&1); mypy_rc=$?
# Timing tests are excluded: they assert wall-clock limits and would flake
# under the load of a hook run. Run them explicitly with `pytest -m timing`.
test_out=$("$py" -m pytest -q -x -m "not timing" -p no:cacheprovider 2>&1); test_rc=$?

if [ $mypy_rc -ne 0 ] || [ $test_rc -ne 0 ]; then
  {
    echo "services/api checks failed after editing ${file#$root/}"
    [ $mypy_rc -ne 0 ] && printf '\n--- mypy ---\n%s\n' "$out"
    [ $test_rc -ne 0 ] && printf '\n--- pytest ---\n%s\n' "$(printf '%s\n' "$test_out" | tail -40)"
  } >&2
  exit 2
fi
exit 0
