#!/bin/sh
# PostToolUse / PostToolUseFailure(Bash): record the command and $1, succeeded or failed,
# as hooks.json maps the two hooks, against the subject, while an Ask is open. Never its
# output. Never blocks the turn; silent without the CLI.
command -v ringframe >/dev/null 2>&1 || exit 0
ringframe fact --host claude-code --from-hook --outcome "$1" >/dev/null 2>&1
exit 0
