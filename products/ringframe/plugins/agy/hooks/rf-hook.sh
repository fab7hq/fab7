#!/bin/sh
# Run one ringframe command on the hook's payload, which arrives on stdin: the
# arguments are the command, as hooks.json names it for this host's hook. Never
# blocks or alters the turn: prints the result Antigravity expects, silently
# without the CLI. `--allow` first is for a hook that must decide: PreToolUse,
# whose reply without a decision Antigravity reads as a deny (1.2.12,
# ringframe-weft-waiting-q01); ask_question needs no permission, so allowing it
# changes nothing but lets it be shown.
reply='{}'
if [ "$1" = --allow ]; then
  reply='{"decision":"allow"}'
  shift
fi
if command -v ringframe >/dev/null 2>&1; then
  ringframe "$@" >/dev/null 2>&1
fi
printf '%s\n' "$reply"
exit 0
