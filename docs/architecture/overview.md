---
title: Fab7 Architecture
type: architecture
status: implemented
owner: architecture
last_updated: 2026-07-22
authority_for:
  - runtime boundary
  - component responsibilities
  - public commands
---

# Fab7 architecture

The Fab7 proof core is one dependency-free Python package and one optional
GitHub Action. A thin distribution layer owns deterministic releases, global
and project installation, two host integrations, and external extension
distribution. There is still no service, database, daemon, provider adapter,
or extension runtime in core.

## Complete flow

```text
fab7 claim
    -> append claim to .fab7/records/<work-item>.jsonl

fab7 verify -- <argv>
    -> require clean implementation state
    -> execute argv without a shell
    -> hash stdout and stderr
    -> append evidence linked to the claim and tested commit

fab7 ci-check
    -> validate every ledger
    -> reject non-append changes
    -> select the latest claim
    -> require linked exit-0 evidence
    -> reject evidence followed by implementation changes
```

## Modules

| Module | Responsibility |
|---|---|
| `cli.py` | argument parsing, output, and exit status |
| `ledger.py` | two record types, command execution, validation, atomic append |
| `gate.py` | append-only and latest-claim freshness decision |
| `git.py` | bounded Git subprocess calls |
| `errors.py` | stable failure and result envelopes |
| `install.py` | closed release and project manifests, global selection, project pinning, repair, and dispatch |
| `hosts.py` | literal bounded Claude Code and Codex plugin registration commands |
| `extensions.py` | catalog refresh/list plus immutable install, diagnosis, host lifecycle, and uninstall |
| `extension_package.py` | closed local-source, ZIP package, file, identity, compatibility, and receipt validation |

Dependencies point inward to these literal functions. There is no interface
hierarchy because no second implementation exists.

## Public commands

```text
fab7 init
fab7 install claude|codex
fab7 ext refresh
fab7 ext list [--refresh] [--catalog PATH]
fab7 ext install NAME --host HOST [--catalog PATH]
fab7 ext install --local PATH --host HOST
fab7 ext doctor
fab7 ext uninstall NAME --host HOST
fab7 claim --work-item ID --summary TEXT
fab7 verify --work-item ID --claim RECORD_ID -- COMMAND [ARGS...]
fab7 ci-check [--work-item ID] [--base REF] [--head REF]
fab7 audit [--work-item ID]
fab7 doctor
```

The GitHub Action builds the selected action revision, validates it against the
tracked project pin, repairs the ignored local executable, and invokes
`fab7 ci-check`; it has no independent policy or provider behavior.

## Onboarding boundary — implemented and owner-accepted

The implemented local-source path adds a thin Fab7 installation plane without
changing the dependency direction of the proof core:

```text
install.sh
    -> build and install Fab7 beneath ~/.fab7/

fab7 install claude|codex
    -> register a bundled, thin Fab7 host plugin through native host commands

Fab7 host skill
    -> invoke the stable ~/.fab7/bin/fab7 dispatcher

fab7 init
    -> copy a version-pinned executable to <repo>/.fab7/bin/fab7
    -> keep the generated executable separate from tracked proof records

fab7 claim|verify|ci-check|audit|doctor
    -> validate the tracked project contract and executable digest
    -> execute <repo>/.fab7/bin/fab7
```

The ledger and gate modules do not depend on the installer or host plugins. The
onboarding plane coordinates files and native host subprocesses; it does not
accept agent prose as state. The user-global installation owns bootstrap and
host registration; the project-local installation owns the selected Fab7
executable for that repository. Only `.fab7/records/` remains proof history.

The extension plane refreshes a closed catalog from
[`fab7hq/ext-registry`](https://github.com/fab7hq/ext-registry) and accepts
either a registry name or an explicitly approved local source path. Both
converge on one verified immutable installed-package layout and native host
integration. Local development installs are digest-bound snapshots, not live
links. [`fab7hq/muslin`](https://github.com/fab7hq/muslin) proves the boundary
by calling Fab7 only through its public binary; Denim remains deferred.

[`distribution.md`](distribution.md) owns the bootstrap, repository, layout,
catalog, package, host, lifecycle, and release-evidence contracts. Extension
distribution is released. Managed Fab7 and extension marketplace upgrades use
the exact family boundaries defined there; unrelated same-name marketplaces
still fail closed. Release `v0.2.1` is the first released implementation of
that migration contract.

See [`ledger.md`](ledger.md) for the persisted record and gate contract.
