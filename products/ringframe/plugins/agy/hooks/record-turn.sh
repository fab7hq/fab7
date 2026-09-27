#!/bin/sh
# Record the agent's state for Weft: $1 is working, waiting or turn_ended, as hooks.json
# maps Antigravity's hooks to them (waiting: its ask_question tool, a candidate under
# qualification); it has none for ready. Keeps only
# the session id and the time. Antigravity runs a hook from the plugin's own directory and
# its payload names no cwd, so the workspace is taken from the payload's workspacePaths.
# Never blocks or alters the turn: prints the result Antigravity expects, silently without
# the CLI. $2 is that result for a hook that must decide: `allow` for PreToolUse, whose
# reply without a decision Antigravity reads as a deny (1.2.12, ringframe-weft-waiting-q01).
# ask_question needs no permission, so allowing it changes nothing but lets it be shown.
payload=$(cat)
if command -v ringframe >/dev/null 2>&1; then
  ws=$(printf '%s' "$payload" | tr -d '\n' | sed -n 's/.*"workspacePaths"[[:space:]]*:[[:space:]]*\[[[:space:]]*"\([^"]*\)".*/\1/p')
  if [ -n "$ws" ]; then
    printf '%s' "$payload" | ringframe --workspace "$ws" sessions turn --from-hook --host agy --event "$1" >/dev/null 2>&1
  fi
fi
if [ "$2" = allow ]; then
  printf '{"decision":"allow"}\n'
else
  printf '{}\n'
fi
exit 0
