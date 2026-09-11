#!/bin/sh
# PostToolUse(EnterPlanMode): record the native receipt as ask.delivery for the one
# confirmed, undelivered Ask in this session. Never blocks the turn; silent without the CLI.
command -v ringframe >/dev/null 2>&1 || exit 0
ringframe ask delivery --from-hook --json >/dev/null 2>&1
exit 0
