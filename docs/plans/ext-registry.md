---
title: Fab7 Extension Distribution Closure Plan
type: plan
status: completed
implementation_authorized: true
owner: product-and-engineering
last_updated: 2026-07-22
repositories:
  - https://github.com/fab7hq/fab7
  - https://github.com/fab7hq/ext-registry
  - https://github.com/fab7hq/muslin
authority_for:
  - extension distribution implementation boundary
  - work packages and proof
  - publication order and stop rules
depends_on:
  - docs/product/roadmap.md
  - docs/architecture/distribution.md
---

# Fab7 extension distribution closure plan

Implementation was authorized on 2026-07-20 and expanded to include explicit
local extension development. Muslin was authorized as the minimal external
fixture. The owner authorized release on 2026-07-22, and implementation,
publication, hosted CI, and the fresh network observation completed the same
day.

## Outcome

The finite outcome is one durable extension path:

1. refresh and validate the reviewed registry without losing the
   last-known-good catalog;
2. discover catalog and installed extension state through the Fab7 CLI and thin
   Claude/Codex surfaces;
3. install either one registry name or one explicitly approved local source
   through the same verified immutable package contract;
4. expose the extension executable under `~/.fab7/bin` and activate its native
   host plugin;
5. diagnose selected and inactive snapshots; and
6. remove one host integration at a time, deleting package state only after the
   final host is removed.

Muslin proves the boundary by running `fab7 --version`. Denim, third-party
submission, dependency solving, background updates, and a generic extension
runtime are excluded.

## Completed work packages

| Package | Implemented outcome |
|---|---|
| ER0 catalog | Closed JSON-compatible YAML v1; canonical fields, ordering, compatibility, GitHub release URL, and digest validation. |
| ER1 refresh/list | GitHub contents response validation, blob/content lock record, rollback rejection, atomic last-known-good replacement, local catalog override, installed-state listing. |
| ER2 package | Closed source, package, archive, receipt, file mode/digest, host-root, origin, and compatibility contracts with bounded non-shell local build. |
| ER3 lifecycle | Immutable registry and `dev-<source-digest>` snapshots, atomic selector, mutation lock, native host activation, idempotency, single-host migration and rollback, diagnosis, and multi-host uninstall. |
| ER4 host surfaces | `/fab7:ext-list`, `/fab7:ext-install`, `$fab7:ext-list`, and `$fab7:ext-install` delegate to the CLI and preserve local-build approval. |
| ER5 Muslin | External deterministic `0.1.0` fixture, Claude command, Codex skill, public-binary interaction, tests, license, and reproducible ZIP. |
| ER6 registry | External metadata-only registry with the exact Muslin release URL and SHA-256 entry plus CI pinned to released Fab7 `v0.2.0`. |

## Proof completed on 2026-07-22

- 55 focused extension, catalog, host, and CLI tests and the complete 75-test
  Fab7 suite passed after lifecycle hardening.
- Muslin's unit suite passed and two independent package builds produced the
  same bytes and SHA-256
  `4b105587a409d275fdf2a1712db6706a093ec0ad6fcfa42d6c7c022fcd93f9a1`.
- The exact local registry entry and those ZIP bytes completed the registry
  installer path with version `0.1.0`, registry origin, matching artifact
  digest, and a healthy installed receipt.
- A fresh isolated macOS home installed Fab7 `0.2.0` from source and registered
  `fab7@fab7` in Claude Code `2.1.217` and Codex CLI `0.144.6`.
- The same home installed Muslin from its local source into both hosts. Both
  hosts reported the plugin enabled; `fab7 ext doctor` reported one healthy
  snapshot with both integrations; `muslin start --json` observed Fab7
  `0.2.0`.
- Uninstalling Claude removed only that integration and preserved the Codex
  plugin, selector, package, healthy diagnosis, and executable. Uninstalling
  Codex then removed the final selector and package while leaving Fab7 host
  plugins intact.

Two independent Fab7 release builds matched, the built executable reported
`0.2.0`, shell syntax and local catalog validation passed, and repository-local
documentation links resolved. The final worktree audit remains part of the
release handoff.

Hosted CI passed for Fab7, Muslin on Python 3.11 across Ubuntu and macOS, and
the registry against the exact released Fab7 `v0.2.0` installer.

## Publication completed

Publication completed in dependency order because each later identity names an
earlier immutable release:

1. [Fab7 `v0.2.0`](https://github.com/fab7hq/fab7/releases/tag/v0.2.0) with
   its source checksum asset; CI run
   [`29914449524`](https://github.com/fab7hq/fab7/actions/runs/29914449524)
   passed.
2. [Muslin `v0.1.0`](https://github.com/fab7hq/muslin/releases/tag/v0.1.0)
   with the validated `muslin-0.1.0.zip`; Ubuntu and macOS CI run
   [`29914582862`](https://github.com/fab7hq/muslin/actions/runs/29914582862)
   passed.
3. [ext-registry `v0.1.0`](https://github.com/fab7hq/ext-registry/releases/tag/v0.1.0)
   with CI pinned exactly to Fab7 `v0.2.0`; run
   [`29914650345`](https://github.com/fab7hq/ext-registry/actions/runs/29914650345)
   passed.

## Network acceptance completed

The fresh isolated macOS observation ran:

```text
fab7 ext refresh --json
fab7 ext list --json
fab7 ext install muslin --host claude|codex --json
fab7 ext doctor --json
muslin start --json
fab7 ext uninstall muslin --host claude|codex --json
```

The public installer produced Fab7 `0.2.0`. Refresh retained registry blob
`0c43de37b2ea4a6c73d665d9b904105a3332aef8` and content SHA-256
`27d3986ab65ac92c1d85022af51cbbe62b063745eae63e4d282c28c0827e429b`.
The receipt recorded registry origin, catalog `0.1.0`, Muslin `0.1.0`, and the
expected artifact digest. Both host CLIs reported Fab7 and Muslin enabled;
`muslin start --json` observed Fab7 `0.2.0`; doctor was healthy. Partial
uninstall retained the Codex integration, selector, package, and executable.
Final uninstall removed the Muslin selector and package while both Fab7 host
plugins remained enabled.

## Stop rules

- Do not publish a catalog entry before its exact release bytes exist.
- Do not change the catalog or package schema during release preparation.
- Do not substitute a moving branch archive, `releases/latest`, mutable local
  link, install hook, or implicit source execution.
- Do not migrate another active host when selecting changed extension bytes;
  require explicit uninstall authority first.
- Do not let catalog inclusion or host output become proof authority.
- Do not begin Denim inside this closure plan.
