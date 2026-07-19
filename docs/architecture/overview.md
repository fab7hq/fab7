---
title: Fab7 Architecture
type: architecture
status: implemented
owner: architecture
last_updated: 2026-07-19
authority_for:
  - runtime boundary
  - component responsibilities
  - public commands
---

# Fab7 architecture

The Fab7 proof core is one dependency-free Python package and one optional
GitHub Action. The repository now also contains a thin onboarding layer: a
deterministic release builder, filesystem installer, and two release-bundled
host plugins. There is still no service, database, daemon, provider adapter, or
extension registry.

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

Dependencies point inward to these literal functions. There is no interface
hierarchy because no second implementation exists.

## Public commands

```text
fab7 init
fab7 install claude|codex
fab7 claim --work-item ID --summary TEXT
fab7 verify --work-item ID --claim RECORD_ID -- COMMAND [ARGS...]
fab7 ci-check [--work-item ID] [--base REF] [--head REF]
fab7 audit [--work-item ID]
fab7 doctor
```

The GitHub Action builds the selected action revision, validates it against the
tracked project pin, repairs the ignored local executable, and invokes
`fab7 ci-check`; it has no independent policy or provider behavior.

## Onboarding boundary — partially implemented

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

The separate future extension plane will read `catalog.yaml` from
[`fab7hq/ext-registry`](https://github.com/fab7hq/ext-registry), install Denim
from [`fab7hq/denim`](https://github.com/fab7hq/denim), and let Denim call Fab7
only through public commands and structured output. Neither external repository
is part of the active onboarding plan.

[`distribution.md`](distribution.md) owns the bootstrap, repository, layout,
host, future registry, user-journey, and acceptance contracts. Its
implementation status remains `in_progress` until the versioned network
bootstrap, Linux matrix, and both host-native init invocations have current
evidence.

See [`ledger.md`](ledger.md) for the persisted record and gate contract.
