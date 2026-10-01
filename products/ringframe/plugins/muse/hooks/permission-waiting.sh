#!/bin/sh
# PermissionRequest: run one ringframe command on the hook's payload, which arrives on
# stdin. Never blocks or alters the turn; silent without the CLI.
command -v ringframe >/dev/null 2>&1 || exit 0
ringframe sessions turn --from-hook --host muse --event waiting >/dev/null 2>&1
exit 0
