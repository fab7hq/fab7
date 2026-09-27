#!/bin/sh
# Record the agent's state for Weft: $1 is ready, working, waiting or turn_ended, as
# hooks.json maps this host's hooks to them. Keeps only the session id and the time.
# Never blocks or alters the turn; silent without the CLI.
command -v ringframe >/dev/null 2>&1 || exit 0
ringframe sessions turn --from-hook --host codex --event "$1" >/dev/null 2>&1
exit 0
