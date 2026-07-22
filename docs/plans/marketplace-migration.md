---
title: Managed Marketplace Migration
type: plan
status: completed
implementation_authorized: true
publication_authorized: true
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
name collision. Release `v0.2.1` corrects that boundary for Fab7 and installed
extensions.

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
- Fresh isolated macOS homes registered released Fab7 `0.1.0` and `0.2.0`,
  installed the `0.2.1` source candidate, and observed `status: migrated` plus
  enabled `fab7@fab7` version `0.2.1` in Claude Code `2.1.217` and Codex CLI
  `0.144.6`. Repeating each install returned `already_installed`.
- The same boundary migrated real Claude and Codex Muslin marketplaces from
  local version `0.1.0` to `0.1.1`. Both hosts reported the new root and plugin
  version, `ext doctor` reported two valid snapshots with only the new one
  integrated, and `muslin start` observed Fab7 `0.2.1`.
- The release build is deterministic, shell syntax passes, and documentation
  status, links, and diff hygiene remain release gates.

## Release closure

The owner authorized publication on 2026-07-22. Tag and release `v0.2.1` point
to commit `2f6d588f721a16fbce2dfe60a19ffb7137e36401`; hosted CI passed on that
exact commit. The release publishes checksum asset
`fab7-0.2.1.source.sha256`, and an independent download verified the tag
archive against SHA-256
`ba8f46b8147f9ad8b4459aa3709b71bb7b31ab9917ea56f4ce2e414048564ef8`.

A fresh isolated macOS home installed released `v0.2.0`, registered both native
hosts, then installed `v0.2.1` through the tagged one-line command. Codex and
Claude each reported `migrated`, exposed enabled plugin version `0.2.1`, and
reported `already_installed` on repetition. With the released `v0.2.1` binary,
Codex also migrated Muslin from registry release `0.1.0` to a reviewed local
`0.1.1` snapshot; `ext doctor` passed with two valid snapshots, the native host
reported plugin `0.1.1`, and `muslin start` observed Fab7 `0.2.1`.

The README keeps the one-line command explicit: the user chooses a published
immutable tag and substitutes it for `vX.Y.Z`. No independent Linux release
migration was observed.
