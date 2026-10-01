#!/bin/sh
# Run one ringframe command on the hook's payload, which arrives on stdin: the
# arguments are the command, as hooks.json names it for this host's hook. Never
# blocks or alters the turn; silent without the CLI.
command -v ringframe >/dev/null 2>&1 || exit 0
ringframe "$@" >/dev/null 2>&1
exit 0
