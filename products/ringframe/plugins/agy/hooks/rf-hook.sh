#!/bin/sh
# Run one ringframe command on the hook's payload, which arrives on stdin: the
# arguments are the command, as hooks.json names it for this host's hook. Never
# blocks or alters the turn: prints the result Antigravity expects, silently
# without the CLI. `--allow` first is for a hook that must decide: PreToolUse,
# whose reply without a decision Antigravity reads as a deny (1.2.12,
# ringframe-weft-waiting-q01); ask_question needs no permission, so allowing it
# changes nothing but lets it be shown. Antigravity runs a hook from the
# plugin's own directory and its payload names no cwd, so the workspace is
# taken from the payload's workspacePaths.
reply='{}'
if [ "$1" = --allow ]; then
  reply='{"decision":"allow"}'
  shift
fi
payload=$(cat)
if command -v ringframe >/dev/null 2>&1; then
  ws=$(printf '%s' "$payload" | tr -d '\n' | sed -n 's/.*"workspacePaths"[[:space:]]*:[[:space:]]*\[[[:space:]]*"\([^"]*\)".*/\1/p')
  if [ -n "$ws" ]; then
    printf '%s' "$payload" | ringframe --workspace "$ws" "$@" >/dev/null 2>&1
  fi
fi
printf '%s\n' "$reply"
exit 0
