#!/bin/sh
# UserPromptSubmit (Grok Build): store the exact bytes of a /rf- invocation so `ringframe ask compile`
# can verify the source intent. Never blocks or alters the turn; silent without the CLI.
command -v ringframe >/dev/null 2>&1 || exit 0
ringframe sessions capture --host grok --host-version "$(grok --version 2>/dev/null)" >/dev/null 2>&1
exit 0
