#!/bin/sh
# PostToolUse / PostToolUseFailure(Bash): record whether the command succeeded, against
# the subject, while an Ask is open. Never its output. Never blocks the turn; silent
# without the CLI.
command -v ringframe >/dev/null 2>&1 || exit 0
ringframe fact --host claude-code --from-hook >/dev/null 2>&1
exit 0
