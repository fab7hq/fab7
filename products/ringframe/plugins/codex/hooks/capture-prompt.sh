#!/bin/sh
# UserPromptSubmit (Codex): store the exact bytes of a $rf: invocation so `ringframe ask compile`
# can verify the source intent, and the digest of every other prompt so a pasted prompt.txt is
# recorded as an observed submission. Never blocks or alters the turn; silent without the CLI.
command -v ringframe >/dev/null 2>&1 || exit 0
ringframe sessions capture --host codex --host-version "$(codex --version 2>/dev/null)" --json >/dev/null 2>&1
exit 0
