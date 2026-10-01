#!/bin/sh
# PreToolUse on request_user_input: run one ringframe command on the hook's payload, which
# arrives on stdin; a native Muse hook has no matcher, so other tools are let
# by here. Never blocks or alters the turn; silent without the CLI.
payload=$(cat)
case "$payload" in *'"tool_name":"request_user_input"'*) ;; *) exit 0 ;; esac
command -v ringframe >/dev/null 2>&1 || exit 0
printf '%s' "$payload" | ringframe sessions turn --from-hook --host muse --event waiting >/dev/null 2>&1
exit 0
