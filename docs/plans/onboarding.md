---
title: Fab7 Onboarding Implementation Plan
type: plan
status: in_progress
implementation_authorized: true
owner: engineering
last_updated: 2026-07-20
authority_for:
  - onboarding implementation sequence
  - onboarding work-package gates
  - onboarding verification and closure
depends_on:
  - docs/product/roadmap.md
  - docs/architecture/distribution.md
---

# Fab7 onboarding implementation plan

This plan delivers only the Fab7-owned onboarding path. Implementation was
authorized on 2026-07-19; work-package exit gates still require current
evidence before any target command is reported as complete. The extension
registry and Denim are explicitly deferred.

## Outcome

From a supported fresh user account, the user can:

1. run a versioned `install.sh` and obtain `fab7` from `~/.fab7/bin`;
2. run `fab7 install claude` or `fab7 install codex`;
3. open the selected host and initialize a Git repository through `/fab7:init`
   or `$fab7:init`; and
4. obtain the exact tracked and ignored `.fab7/` layout and execute proof
   commands through its pinned local Fab7 executable.

The phase closes only after both Claude Code and Codex complete this Fab7-only
journey with fresh evidence.

## Fixed implementation boundary

- Fab7 repository: [`fab7hq/fab7`](https://github.com/fab7hq/fab7).
- Platforms: macOS and Linux.
- Shell installer and startup files: Bash and Zsh.
- Runtime prerequisite: Python 3.11 or newer.
- Hosts: Claude Code and Codex CLI.
- Artifact: one deterministic executable Python archive with no runtime
  dependency beyond Python and the standard library.
- Onboarding-state global layout: only `bin/` and `runtime/` beneath
  `~/.fab7/`.
- Project layout: `project.json`, `.gitignore`, `records/`, and ignored
  `bin/fab7` beneath `<repo>/.fab7/`.

The release contract is fixed as tag `v<VERSION>`, source archive
`https://github.com/fab7hq/fab7/archive/refs/tags/v<VERSION>.tar.gz`, and
checksum asset
`https://github.com/fab7hq/fab7/releases/download/v<VERSION>/fab7-<VERSION>.source.sha256`.
The `v0.1.0` tag and checksum asset close publication identity. Default-network
acceptance remains a WP4 gate.

## Deferred repositories

- [`fab7hq/ext-registry`](https://github.com/fab7hq/ext-registry) will later own
  `catalog.yaml` and its registry contract.
- [`fab7hq/denim`](https://github.com/fab7hq/denim) will later own the first
  extension runtime and host plugins.

This plan does not create, populate, test, release, or integrate either
repository. It does not add `fab7 ext` commands, `~/.fab7/catalog.yaml`,
`~/.fab7/extensions/`, Denim launchers, or Denim host skills.

## Non-goals

Do not add Windows, Fish, a daemon, service, package manager, generic host
registry, compatibility framework, persistent cache, receipt store, staging
directory, lock directory, extension implementation, auto-update, or another
record type.

## Planned source shape

Add only structures earned by the accepted path:

```text
install.sh
scripts/
├── build_zipapp.py
└── zipapp_main.py
core/fab7/
├── cli.py
├── install.py
└── hosts.py
plugins/
├── claude/fab7/...
└── codex/fab7/...
core/tests/
├── test_artifact.py
├── test_distribution.py
└── test_hosts.py
```

`install.py` owns global and project layouts, release manifests, installation
transactions, and command dispatch. `hosts.py` contains literal Claude Code and
Codex command functions; it is not an adapter hierarchy. Split a module only if
focused tests demonstrate a second current responsibility.

## Current implementation evidence

The following evidence applies to the source tree and generated executable
identified here. Any package, launcher, plugin, or builder change requires a
fresh artifact identity and host observation.

| Area | Current result | Remaining gate |
|---|---|---|
| WP0 release artifact | Implemented; duplicate builds match, the archive executes outside the checkout, the manifest validates digest `sha256:1f3d4bcb6de5424472ae4b3ce8bbcaf65fc54c718bf89e016b8add16f575a394`, and tag `v0.1.0` has a matching source checksum asset. | Prove the default download path. |
| WP1 global install | Local-source install and same-version rerun passed in disposable macOS Bash and Zsh homes; failure and profile rollback tests pass; final `~/.fab7/` contains only `bin/` and `runtime/`. | Run the published archive path on macOS and Linux and complete the remaining failure matrix. |
| WP2 project install | New init, proof-command dispatch, digest rejection, binary repair, committed-project clone repair, and action-style repair passed. | Complete the remaining symlink, permission, unsupported-pin, and interrupted-mutation matrix on the release candidate. |
| WP3 host plugins | Claude Code 2.1.214 and Codex CLI 0.144.5 accepted the bundled marketplaces; `fab7@fab7` was installed, discovered, enabled, and idempotent in isolated host homes. | Invoke `/fab7:init` and `$fab7:init` from fresh authenticated host sessions against the exact released artifact. |
| WP4 closure | `28` deterministic tests, build determinism, strict Claude validation, Codex plugin validation, shell syntax, project proof execution, and clone/action repair passed on 2026-07-19. | Linux, published-release bootstrap, both host-native invocations, and final release evidence are not run. |

The disposable evidence root is `../sandbox/onboarding-v4/`. Its release
manifest records source digest
`sha256:1e364b9c5d3895bffa5de33e9cf3c1b168a94369a98fa1f6dba3892418c1d005`.
Sandbox state is evidence input, not a shipped artifact or repository authority.

## Work packages

### WP0 — Freeze release identity and deterministic executable

Outcome: one source tree produces one directly executable Fab7 archive with
stable behavior and a closed release manifest.

Tasks:

- O001: use tag `v<VERSION>`, the GitHub tag archive URL, and release checksum
  asset `fab7-<VERSION>.source.sha256` beneath `fab7hq/fab7`;
- O002: add failing tests that build twice from identical inputs and require
  identical bytes, version output, help output, and exit status;
- O003: add `scripts/zipapp_main.py`, copied to the archive root as
  `__main__.py`, that imports the Fab7 CLI and exits through
  `SystemExit(main())`;
- O004: implement `scripts/build_zipapp.py` with sorted package inputs, fixed
  archive metadata, a `#!/usr/bin/env python3` shebang, executable mode, and no
  tests or checkout-only files in the artifact;
- O005: add a closed Fab7 release-manifest validator with only the fields owned
  by the architecture contract;
- O006: stage and include reviewed Fab7 host-plugin source roots beside the
  executable release without importing host code into core; and
- O007: prove the artifact from outside the checkout with passing and failing
  CLI paths.

Exit gate:

- all release URLs and identities are exact and immutable;
- two clean builds have the same SHA-256 digest;
- the archive runs on supported Python versions without the repository or a
  virtual environment;
- `--version` reports the source version;
- failure paths preserve Fab7's exit codes; and
- the manifest digest matches the executable bytes.

### WP1 — Install Fab7 beneath `~/.fab7/`

Outcome: the repository-owned Bash script installs or reselects one verified
Fab7 version without damaging an earlier installation or shell profile.

Tasks:

- O010: add hermetic tests using a bounded `FAB7_HOME` override and temporary
  shell startup files;
- O011: make `install.sh` validate platform, shell, Git, and Python before
  mutation;
- O012: fetch one versioned source archive and checksum, reject redirects or
  identities outside `fab7hq/fab7`, and verify before building;
- O013: stage only package and host-plugin inputs, then invoke the deterministic
  builder;
- O014: install the immutable version beneath `runtime/<version>/` and select
  it atomically through `bin/fab7`;
- O015: write the release manifest and verify the installed executable before
  selection;
- O016: update Bash or Zsh startup configuration only after installation
  succeeds, using one bounded idempotent block; and
- O017: return a truthful reload instruction because a child script cannot
  modify the parent shell environment.

Exit gate:

- fresh install, same-version rerun, version switch, interrupted build, digest
  failure, missing Python, and unwritable-target tests pass;
- failure leaves the previous selected version and shell startup file intact;
- the steady-state tree contains only `~/.fab7/bin/` and `~/.fab7/runtime/`;
  and
- a reloaded shell resolves the expected `fab7 --version`.

### WP2 — Create and select the project-local installation

Outcome: `fab7 init` creates the four-entry `.fab7/` contract and all proof
commands run through its pinned executable.

Tasks:

- O020: add failing tests for exact tree shape, closed `project.json`, exact
  `.gitignore`, executable digest, permissions, and preserved records;
- O021: extend `fab7 init` to copy the selected verified executable atomically
  into `.fab7/bin/fab7` and write the tracked contract;
- O022: make repeated init repair a missing ignored binary to the existing pin
  without changing the pin or records;
- O023: implement the literal global-versus-project command dispatcher;
- O024: reject symlink escapes, path traversal, unknown manifest keys,
  mismatched digests, non-executable files, unsupported pins, and recursion;
- O025: keep only `.fab7/records/` as proof history while ignored
  `.fab7/bin/` remains absent from Git; and
- O026: update the GitHub Action to install and verify the version pinned by
  `project.json` when that contract exists.

Exit gate:

- new init, repeated init, cloned-project repair, missing global pinned version,
  global-version drift, malformed metadata, and symlink attack tests pass;
- `claim`, `verify`, `ci-check`, `audit`, and `doctor` prove which local
  executable handled the command;
- project initialization never overwrites a ledger; and
- Git sees `project.json`, `.gitignore`, and records but not `bin/fab7`.

### WP3 — Register the Fab7 host plugins

Outcome: `fab7 install claude|codex` installs the release-bundled Fab7 plugin
through the selected host's native user-scoped CLI.

Tasks:

- O030: author the smallest Claude Code plugin exposing only `init` as a thin
  `fab7 init` call;
- O031: author the equivalent Codex plugin skill using native `$fab7:init`
  invocation;
- O032: add deterministic build and drift checks for both bundled host roots;
- O033: implement literal bounded subprocess functions for Claude Code and
  Codex marketplace add, plugin add or install, discovery, and removal;
- O034: add `fab7 install {claude,codex}` with structured output and stable
  `installed`, `already_installed`, and `failed` results;
- O035: fail before mutation when the host is missing, unsupported, or the
  bundled artifact is invalid; and
- O036: report the host's required reload or new-session action without
  claiming activation early.

Exit gate:

- host command construction, timeout, output-bound, failure, idempotency, and
  discovery tests pass;
- host configuration is changed only through supported native commands;
- the installed plugin invokes the global dispatcher; and
- one bounded live install and init per host confirms native discovery and the
  project-local installation.

### WP4 — Prove onboarding and close the phase

Outcome: current, scope-matching evidence proves both Fab7-only user journeys
and the documentation reports limits honestly.

Tasks:

- O040: run the full deterministic suite, executable build check, host artifact
  drift checks, shell syntax check, and `git diff --check`;
- O041: run installation from a versioned release in clean disposable macOS and
  Linux user state for Bash and Zsh;
- O042: run the fresh Claude Code journey through installation, host
  registration, `/fab7:init`, and one project proof command;
- O043: run the fresh Codex journey through installation, host registration,
  `$fab7:init`, and one project proof command;
- O044: prove project cloning and pinned-local-executable repair on a second
  disposable checkout;
- O045: record exact release, executable, and host artifact identities plus
  every pass, failure, not-run gate, and residual platform limit; and
- O046: update product, architecture, status, install documentation, and the
  active plan together only after the complete exit gate passes.

Exit gate:

```bash
uv run python -m pytest
python scripts/build_zipapp.py --check
bash -n install.sh
git diff --check
```

Those deterministic gates plus the four fresh platform and shell bootstrap
checks and two live host journeys must pass. A component test, host CLI success
message, or prior artifact observation cannot close the phase by itself.

## Dependency order

```text
WP0 artifact
  -> WP1 global install
  -> WP2 project install and dispatch
  -> WP3 Fab7 host plugins
  -> WP4 fresh acceptance and closure
```

Work packages may overlap only after their predecessor's public contract is
fixed. No later package may widen an earlier authority boundary to make its own
gate pass.

## Stop rules

- Stop published-release acceptance while the exact tag or checksum asset is
  absent or mutable.
- Stop a mutation before selection when validation is incomplete or ambiguous.
- Preserve the previous global version, project pin, and host state on failure.
- Do not call the phase complete while either supported host journey or any
  named deterministic gate is failed or not run.
- Do not implement `ext-registry`, Denim, or any `fab7 ext` command as part of
  this plan.
