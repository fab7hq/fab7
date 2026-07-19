---
title: Fab7 Product Roadmap
type: product
status: accepted
owner: product
last_updated: 2026-07-19
authority_for:
  - completed product capability
  - current exclusions
  - accepted next delivery outcome
  - deferred extension products
---

# Fab7 product roadmap

## Lean baseline — complete

The repository contains one complete path:

- initialize `.fab7/records/`;
- append one of two closed record types: `claim` or `evidence`;
- execute verification commands directly without a shell;
- bind evidence to the tested Git commit and an output digest;
- require fresh passing evidence for the latest claim;
- reject malformed records, history rewrites, and post-verification code
  changes;
- inspect one work item with `audit` and validate setup with `doctor`; and
- run the same gate through the small GitHub composite action.

The runtime uses only the Python standard library. A focused regression suite
protects the ledger, gate, command execution, action, and full CLI path.

## Fab7 onboarding — in progress

The next accepted outcome is a Fab7-only path from a fresh user account to a
project-pinned installation in Claude Code or Codex:

```text
run the Fab7 bootstrap script
    -> build and install Fab7 beneath ~/.fab7/
    -> reload the shell so ~/.fab7/bin is on PATH

fab7 install claude|codex
    -> register the bundled Fab7 plugin through the host's native CLI

invoke /fab7:init or $fab7:init
    -> invoke the user-global Fab7 binary
    -> create a pinned project-local Fab7 installation beneath .fab7/
    -> initialize or preserve .fab7/records/

invoke a proof command
    -> validate the project contract and executable digest
    -> execute the project-pinned Fab7 binary
```

### Accepted scope

- [`fab7hq/fab7`](https://github.com/fab7hq/fab7) owns `install.sh`, release
  artifacts, the CLI, bundled Fab7 host plugins, and onboarding contracts;
- `install.sh` fetches one immutable Fab7 release, verifies it, builds it in an
  operating-system temporary directory, installs it beneath `~/.fab7/`,
  atomically exposes `~/.fab7/bin/fab7`, and idempotently adds that bin
  directory to the detected shell's startup `PATH`;
- `fab7 install claude` and `fab7 install codex` install the bundled Fab7 host
  plugin through each host's supported marketplace and plugin commands;
- `fab7 init` uses the verified user-global installation to create a second,
  version-pinned project installation at `.fab7/bin/fab7`, keeps generated
  executable files ignored, and preserves `.fab7/project.json`,
  `.fab7/.gitignore`, and `.fab7/records/` as repository-owned state; and
- proof commands fail closed when the tracked pin, local executable, digest,
  permissions, or path boundary is missing or invalid.

The detailed component, trust, state, and host contracts live in
[`../architecture/distribution.md`](../architecture/distribution.md).

### Current implementation

The repository now contains the deterministic release builder, local-source
bootstrap, global and project manifest validation, pinned executable repair and
dispatch, action integration, release-bundled Claude Code and Codex plugins,
and native idempotent host registration. These are implemented contracts, not
phase closure: the exact evidence and residual gates are recorded in the
[`active plan`](../plans/onboarding.md#current-implementation-evidence).

### Exit gate

The phase remains incomplete until fresh disposable user state proves:

- repeatable install and shell activation on supported macOS and Linux Bash and
  Zsh environments;
- native Fab7 plugin installation and discovery in Claude Code and Codex;
- `/fab7:init` and `$fab7:init` atomically create the project-local executable,
  select it for proof commands, reject mismatched or symlinked local state, and
  leave only the project manifest, ignore rules, and proof records eligible for
  Git;
- reinstallation and project repair are idempotent, while failure preserves the
  previous installation, records, shell profile, and unrelated host state; and
- documentation records exact versions, checks, failures, not-run gates, and
  remaining platform limits.

Implementation was authorized on 2026-07-19. The active finite plan is
[`../plans/onboarding.md`](../plans/onboarding.md); completion still requires
its exact deterministic and live-host exit gates.

## `ext-registry` and Denim — deferred

Extension discovery and the first extension are separate follow-on products:

- [`fab7hq/ext-registry`](https://github.com/fab7hq/ext-registry) will own one
  reviewed, versioned `catalog.yaml` and no extension runtime artifacts;
- [`fab7hq/denim`](https://github.com/fab7hq/denim) will own the first extension
  runtime, manifest, host plugins, release artifacts, checksums, and tests;
- `fab7 ext list`, `install`, `doctor`, and `uninstall` will provide the
  deterministic binary path behind the future host skills; and
- Denim will call Fab7 only through its public binary and structured output.

Neither repository is implemented by the active onboarding plan. Before this
phase starts, product and engineering must accept the `catalog.yaml` schema and
parser boundary, immutable registry refresh URL, extension release contract,
and current Claude Code and Codex activation behavior.

Its eventual complete journey is:

```text
/fab7:ext-list or $fab7:ext-list
    -> validate ~/.fab7/catalog.yaml from fab7hq/ext-registry

/fab7:ext-install denim or $fab7:ext-install denim
    -> install a verified prebuilt release from fab7hq/denim
    -> register the release-bundled host plugin

/denim:start or $denim:start
    -> execute the installed Denim binary
    -> reach project-pinned Fab7 only through the stable fab7 command
```

## Still excluded

There is no generic record framework, configurable policy engine, fabric
registry, planning or orchestration layer, provider registry, service,
performance suite, or comparative agent evaluation. Distribution also excludes
third-party submission, ratings, ranking, catalog federation, dependency
solving, background updates, arbitrary install hooks, cross-extension imports,
private registries, and unsupported-host compatibility shims.
