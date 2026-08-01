#!/usr/bin/env bash
# PreToolUse hook: rewrite supported Bash commands to run through the rtk
# proxy (https://github.com/rtk-ai/rtk), which compresses verbose CLI output
# before it reaches the model's context. Requires the `rtk` binary to be
# installed locally (e.g. `curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/master/install.sh | sh`).
# If rtk isn't installed, or the command doesn't match a supported tool, the
# command passes through unchanged.
set -euo pipefail

input=$(cat)

# Only ever touch Bash tool calls.
tool_name=$(jq -r '.tool_name // empty' <<<"$input")
if [[ "$tool_name" != "Bash" ]]; then
  exit 0
fi

command=$(jq -r '.tool_input.command // empty' <<<"$input")
if [[ -z "$command" ]]; then
  exit 0
fi

# rtk must be installed and on PATH.
if ! command -v rtk >/dev/null 2>&1; then
  exit 0
fi

# Already proxied, or empty leading token — leave it alone.
if [[ "$command" =~ ^[[:space:]]*rtk[[:space:]] ]]; then
  exit 0
fi

# Grab the leading command word only; compound commands (&&, ;, |, subshells)
# are left untouched so we never risk mis-rewriting a multi-step pipeline.
leading_word=$(awk '{print $1}' <<<"$command")

case "$leading_word" in
  git|npm|pnpm|yarn|pip|pip3|pytest|cargo|docker|docker-compose|kubectl|go|jest|vitest|rspec|bundle|prisma|eslint|ruff|tsc|prettier|aws|ls|tree|grep|find)
    new_command="rtk ${command}"
    jq -n --arg cmd "$new_command" '{
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "allow",
        updatedInput: { command: $cmd }
      }
    }'
    ;;
  *)
    exit 0
    ;;
esac
