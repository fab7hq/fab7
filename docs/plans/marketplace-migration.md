---
title: Managed Marketplace Migration
type: plan
status: implementation_complete
implementation_authorized: true
owner: product-and-engineering
last_updated: 2026-07-22
authority_for:
  - Fab7 and extension marketplace migration correction
  - migration proof and release gate
depends_on:
  - docs/architecture/distribution.md
---

# Managed marketplace migration

Fab7 `v0.2.0` rejected a legitimate host re-registration when the same
marketplace name still pointed to an older Fab7 release. The literal path
comparison could not distinguish a prior managed version from an unrelated
name collision. The `v0.2.1` maintenance candidate corrects that boundary for
Fab7 and installed extensions.

## Contract

Installation may migrate a different marketplace path only when both paths
belong to the same exact managed family beneath the selected `FAB7_HOME`:

```text
runtime/<version>/hosts/<host>                    # Fab7
extensions/<name>/<install-id>/hosts/<host>       # one extension
```

If the previous root still exists, its contained marketplace and plugin
identity must validate before mutation. Fab7 then removes the prior plugin and
marketplace through the native host CLI, adds the new root, installs and
verifies the plugin, and reports `migrated`. Failure restores and verifies the
previous registration or returns `FAB7_HOST_ROLLBACK_FAILED`.

A missing root outside the exact managed family, an invalid surviving root,
another `FAB7_HOME`, another extension name, or any unrelated source remains
`FAB7_HOST_MARKETPLACE_CONFLICT`. Extension multi-host authority is unchanged:
a command does not migrate a second active host implicitly.

## Proof completed

- The complete deterministic suite passes with 84 tests.
- Focused tests cover Claude and Codex Fab7 release migration, extension
  snapshot migration, unrelated and invalid collisions, new-plugin failure
  rollback, and registry version `0.1.0` to `0.2.0` lifecycle migration.
- A fresh isolated macOS home registered released Fab7 `0.1.0`, installed the
  `0.2.1` source candidate, and observed `status: migrated` plus enabled
  `fab7@fab7` version `0.2.1` in Claude Code `2.1.217` and Codex CLI `0.144.6`.
- The same home migrated a real Codex Muslin marketplace from local version
  `0.1.0` to `0.1.1`. Codex reported the new root and plugin version, `ext
  doctor` reported two valid snapshots with only the new one integrated, and
  `muslin start` observed Fab7 `0.2.1`.
- The release build is deterministic, shell syntax passes, and documentation
  status, links, and diff hygiene remain release gates.

## Release gate

Commit and hosted CI do not publish an immutable release. Publication requires
explicit owner authorization, followed by Fab7 `v0.2.1`, its source checksum
asset, and one fresh network upgrade observation. The README remains pinned to
the released `v0.2.0` until that gate passes.
