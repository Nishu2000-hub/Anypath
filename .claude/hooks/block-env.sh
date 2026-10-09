#!/usr/bin/env bash
# PreToolUse: deny edits to .env files (secrets). Templates such as
# .env.example / .env.sample / .env.template stay editable.
set -uo pipefail

file=$(jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')
name=$(basename -- "$file")

case "$name" in
  .env.example|.env.sample|.env.template) exit 0 ;;
  .env|.env.*|*.env)
    jq -n --arg f "$file" '{
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: ("Editing .env files is blocked by project policy: " + $f + ". Ask the user to change secrets themselves, or edit .env.example instead.")
      }
    }'
    ;;
esac
exit 0
