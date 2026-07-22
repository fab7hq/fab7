---
title: Fab7 Architecture
type: architecture
status: implemented
owner: architecture
last_updated: 2026-07-23
authority_for:
  - runtime boundary
  - component responsibilities
  - public commands
---

# Fab7 architecture

The Fab7 proof core is one dependency-free Python package and one optional
GitHub Action. A thin distribution layer owns deterministic releases, global
and project installation, two host integrations, external extension
distribution, and one generic extension-authoring command with shared host
skills. There is still no
service, database, daemon, provider adapter, or extension runtime in core.

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
| `plugin/adapter.py` | build-time host adapter contract and shared action parsing |
| `plugin/claude_adapter.py` | Claude manifest, marketplace, command, and skill rendering |
| `plugin/codex_adapter.py` | Codex manifest, marketplace, and skill rendering |
| `plugin/build.py` | shared native plugin roots and schema-2 extension package assembly |
| `release_build.py` | deterministic source-release executable and host-root assembly |
| `extension_scaffold.py` | collision-safe rendering of one built-in extension source template |
| `extensions.py` | catalog refresh/list plus immutable install, diagnosis, host lifecycle, and uninstall |
| `extension_package.py` | closed local-source, ZIP package, file, identity, compatibility, and receipt validation |

Dependencies point inward to these literal functions. The proof core has no
interface hierarchy. The distribution build has one earned `HostAdapter`
boundary because Claude and Codex are two current implementations with
different native manifests, marketplaces, invocation syntax, and surfaces.
Adapters generate files only; they grant no runtime authority.

## Public commands

```text
fab7 init
fab7 install claude|codex
fab7 ext refresh
fab7 ext list [--refresh] [--catalog PATH]
fab7 ext create [TARGET] --name NAME --publisher OWNER
fab7 ext build [SOURCE] --host HOST [...] [--output ZIP]
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

The source-candidate `fab7 ext create` command renders one host-neutral built-in
schema-2 source template without overwriting existing files. The shared Claude
and Codex `ext-create` skills resolve source identity, delegate writing to that
command, while the Fab7 release builder injects local progressive-disclosure
copies of this overview, [`distribution.md`](distribution.md), and
[`ledger.md`](ledger.md) into each generated host skill.
`fab7 ext build --host HOST` then selects the target adapters and creates the
closed ZIP; generated source contains no host selection, packaging script, or
host-manifest copies. Tests and builds
run only after human approval, and local installation rebuilds, validates,
snapshots, and activates the source. No scaffold output or model statement
becomes proof state.

Fab7 host plugins also have one source boundary outside core. Four shared
actions (`init`, `ext-create`, `ext-list`, and `ext-install`) are reviewed once
as canonical Agent Skill templates. `plugin/build.py` passes them to the same
Claude and Codex adapters used by schema-2 extension builds.
`core/fab7/release_build.py` consumes those rendered roots when `install.sh`
bootstraps from source. There is no source `scripts/` directory, runtime adapter
registry, or unsupported-host placeholder.

[`distribution.md`](distribution.md) owns the bootstrap, repository, layout,
catalog, package, host, lifecycle, and release-evidence contracts. Extension
distribution is released. Managed Fab7 and extension marketplace upgrades use
the exact family boundaries defined there; unrelated same-name marketplaces
still fail closed. Release `v0.2.1` is the first released implementation of
that migration contract. Release `v0.2.2` adds extension authoring without
changing those runtime contracts.

See [`ledger.md`](ledger.md) for the persisted record and gate contract.
