---
title: Fab7 Onboarding and Extension Distribution
type: architecture
status: accepted
implementation_status: in_progress
owner: architecture
last_updated: 2026-07-20
authority_for:
  - repository ownership
  - user-global and project-local filesystem layouts
  - Fab7 bootstrap installation
  - agentic CLI plugin registration
  - future extension registry and installation boundaries
  - onboarding user journey
---

# Fab7 onboarding and extension distribution

This document defines the target boundary for installing Fab7 at user and
project scope, registering it with supported agentic CLIs, and later adding
extension discovery and installation. Fab7 onboarding implementation is in
progress; only behavior protected by current tests and validation is an
implementation claim. The proof-core boundary remains in
[`overview.md`](overview.md).

The delivery boundary is intentionally split:

1. Fab7 onboarding installs Fab7 globally and per project and registers its
   host plugin.
2. The extension registry and Denim are separate follow-on repositories and
   are not part of the current onboarding implementation plan.

## Repository ownership

| Repository | Status | Owns |
|---|---|---|
| [`fab7hq/fab7`](https://github.com/fab7hq/fab7) | current | proof core, deterministic executable builder, `install.sh`, `fab7` CLI, bundled Fab7 host plugins, and distribution contracts |
| [`fab7hq/ext-registry`](https://github.com/fab7hq/ext-registry) | future | one reviewed `catalog.yaml` registry; no extension source or artifacts |
| [`fab7hq/denim`](https://github.com/fab7hq/denim) | future | the first extension runtime, manifest, host plugins, release artifacts, checksums, and tests |

Additional extensions may later use one repository each. The registry never
vendors extension source, host plugins, or executables. An extension release
contains its runtime and host artifacts together so their versions cannot
drift.

## Layout principles

- `~/.fab7/` is user-owned installation and distribution state. Nothing below
  it is committed to a project.
- `<repo>/.fab7/` contains a tracked project contract and proof records plus one
  ignored generated executable.
- Installed release directories are immutable. Selection happens through the
  stable launchers in `bin/`.
- A package manifest is also its installation receipt; no second receipt store
  repeats the same fact.
- Temporary builds use an operating-system temporary directory and move into
  place atomically. There is no persistent `staging/` directory.
- Locks exist only while a mutation is running. There is no persistent `locks/`
  directory.
- Fab7 stores no secrets, raw host transcripts, host configuration copies, or
  unrelated tool output.

## User-global layout

Fab7 onboarding creates only `bin/` and `runtime/`. The future extension phase
adds `extensions/` and `catalog.yaml` when the user first uses extension
discovery or installation.

```text
~/.fab7/
├── bin/
│   ├── fab7 -> ../runtime/<selected-version>/bin/fab7
│   └── denim -> ../extensions/denim/<selected-version>/bin/denim  # future
├── runtime/
│   └── <fab7-version>/
│       ├── manifest.json
│       ├── bin/
│       │   └── fab7
│       └── hosts/
│           ├── claude/
│           └── codex/
├── extensions/                                                   # future
│   └── denim/
│       └── <extension-version>/
│           ├── manifest.json
│           ├── bin/
│           │   └── denim
│           └── hosts/
│               ├── claude/
│               └── codex/
└── catalog.yaml                                                  # future
```

### Global path ownership

| Path | Phase | Intention |
|---|---|---|
| `bin/` | onboarding | Stable executable names placed on the user's `PATH`; it contains selectors, not implementation source. |
| `bin/fab7` | onboarding | Selected global Fab7 executable and dispatcher for project commands. |
| `runtime/<version>/` | onboarding | One immutable installed Fab7 release. Multiple versions may coexist because projects can pin different versions. |
| `runtime/<version>/manifest.json` | onboarding | Closed installed-release identity: schema, name, version, source digest, executable digest, and supported Python range. |
| `runtime/<version>/bin/fab7` | onboarding | One relocatable, directly executable Fab7 archive built from the dependency-free package. |
| `runtime/<version>/hosts/` | onboarding | Fab7 plugin artifacts bundled with the same Fab7 release. |
| `bin/<extension>` | future extension distribution | Selected user-global extension executable, for example `denim`. |
| `extensions/<name>/<version>/` | future extension distribution | One immutable, verified extension release containing its manifest, runtime executables, and host plugins. |
| `catalog.yaml` | future extension distribution | Last-known-good, fully validated registry document fetched from `fab7hq/ext-registry`. |

The selected Fab7 executable uses the standard Python `zipapp` format with a
`#!/usr/bin/env python3` shebang and a source-owned `__main__.py` that exits with
`SystemExit(main())`. Fab7 requires Python 3.11 or newer and uses no runtime
dependency. The same verified archive can therefore be copied into a project
without copying a virtual environment or embedding checkout-specific paths.

The release manifest remains small:

```json
{
  "schema": 1,
  "name": "fab7",
  "version": "<exact-version>",
  "source_sha256": "sha256:<digest>",
  "executable_sha256": "sha256:<digest>",
  "python": ">=3.11"
}
```

Each `hosts/<host>/` directory is a complete local marketplace root accepted by
that host. Fab7 treats it as a built release artifact rather than interpreting
host metadata at runtime.

## Project-local layout

After `fab7 init`, an initialized repository has four entries beneath
`.fab7/`:

```text
<repo>/.fab7/
├── project.json
├── .gitignore
├── records/
│   └── <work-item>.jsonl
└── bin/
    └── fab7
```

| Path | Git ownership | Intention |
|---|---|---|
| `project.json` | tracked | Closed project contract that pins the Fab7 version and executable digest. |
| `.gitignore` | tracked | Ignores only the generated `/bin/` directory. |
| `records/` | tracked | Existing append-only claim and evidence ledgers. |
| `bin/` | ignored | Generated local installation for the current checkout. |
| `bin/fab7` | ignored | Exact copy of the pinned global Fab7 executable; project proof commands execute this file. |

The tracked contract is intentionally small:

```json
{
  "schema": 1,
  "fab7_version": "<exact-version>",
  "executable_sha256": "sha256:<digest>"
}
```

The tracked ignore rule is exactly:

```gitignore
/bin/
```

There is no project-local extension store, catalog, cache, host plugin,
runtime directory, receipt directory, staging directory, lock directory, log,
or secret file in the first complete path.

## Command resolution

All shell and host callers invoke the stable global `fab7` command. The global
executable owns one literal command split:

| Command | Execution scope |
|---|---|
| `fab7 --version` | selected global executable, or selected local version when reporting project context |
| `fab7 install claude\|codex` | user-global |
| `fab7 init` | global bootstrap acting on the current Git repository |
| `fab7 claim`, `verify`, `ci-check`, `audit`, `doctor` | validated `<repo>/.fab7/bin/fab7` |
| `fab7 ext ...` | future user-global extension distribution state |

```text
host plugin or shell
        |
        v
~/.fab7/bin/fab7
        |
        +-- install/init -------> global runtime, hosts, project bootstrap
        |
        +-- project command ----> validate project.json and executable digest
        |                         -> exec .fab7/bin/fab7
        |                         -> read or append .fab7/records/
        |
        +-- future ext command -> catalog.yaml and extensions/
```

The local executable detects that it already runs from `.fab7/bin/fab7` and
does not dispatch again. If `project.json` exists but the local executable is
missing, mismatched, non-executable, or symlinked outside the project, project
commands fail with a stable instruction to run `fab7 init`; they never fall
back silently to a different global version.

For a new project, `fab7 init` selects the current verified global release,
writes `project.json` and `.gitignore`, creates `records/`, copies the executable
atomically into `bin/fab7`, and validates its digest. For an existing project it
preserves records and the tracked pin, resolves that exact version from
`~/.fab7/runtime/`, and repairs only the ignored executable. Changing the pin is
not an implicit side effect of initialization.

CI reads the tracked version contract, installs the exact release in the
runner, and evaluates the committed ledger. It does not use the ignored project
executable.

## Bootstrap installation

The repository-owned `install.sh` performs one bounded transaction:

1. require macOS or Linux, Bash or Zsh startup configuration, Git, and Python
   3.11 or newer;
2. resolve tag `v<VERSION>` from `https://github.com/fab7hq/fab7`;
3. fetch `https://github.com/fab7hq/fab7/archive/refs/tags/v<VERSION>.tar.gz`
   and checksum asset
   `https://github.com/fab7hq/fab7/releases/download/v<VERSION>/fab7-<VERSION>.source.sha256`;
4. verify the source before building;
5. stage only the Fab7 package, a source-owned `__main__.py`, and reviewed host
   plugin sources in an operating-system temporary directory;
6. build and test the executable archive;
7. write its release manifest;
8. atomically install the immutable version under `~/.fab7/runtime/` and select
   it through `~/.fab7/bin/fab7`;
9. only after installation succeeds, add one bounded, idempotent
   `~/.fab7/bin` block to the detected shell startup file; and
10. print the exact login-shell or `source` action needed before the parent
    shell can observe the new `PATH`.

The script cannot change its parent shell's environment. Re-running the same
version is idempotent. A failed fetch, verification, build, smoke test, or
selection leaves the prior installation and shell startup file unchanged.

## Host registration

Bootstrap and host registration are separate explicit actions:

```text
fab7 install claude
fab7 install codex
```

The selected global runtime registers its bundled local marketplace through the
host's native CLI. Each command verifies the host executable and bundled
artifact, shows the user-scoped mutation, bounds subprocess time and retained
output, uses native configuration commands, verifies discovery, and returns
`installed`, `already_installed`, or `failed` with one activation action.

The host plugin is thin: `/fab7:init` in Claude Code and `$fab7:init` in Codex
invoke the deterministic `fab7 init` command and render its structured result.

## Implemented onboarding subset

The current repository implements the local-source form of this architecture:

- `scripts/build_zipapp.py` produces a deterministic executable and complete
  Claude Code and Codex marketplace roots;
- `install.sh --source <reviewed-checkout>` validates prerequisites, builds
  before mutation, installs an immutable version, atomically selects it, and
  updates one shell PATH block after success;
- `fab7 init` creates or validates `project.json`, preserves records, copies and
  verifies the ignored local executable, and repairs it to the existing pin;
- proof commands invoked through the global selector validate and dispatch to
  the project executable;
- `fab7 install claude|codex` validates the bundled root, uses the native host
  CLI, verifies discovery, is idempotent, and reports the activation boundary;
  and
- the composite action builds its selected revision and requires the consumer
  project pin to match before running `ci-check`.

The `v0.1.0` tag and source checksum asset establish the default network
installer path. Network bootstrap, Linux bootstrap, and actual host-session
invocation of `/fab7:init` and `$fab7:init` against that exact release are not
yet evidence-backed. [`../plans/onboarding.md`](../plans/onboarding.md) owns
the exact current evidence and remaining gates.

## Future `ext-registry` and Denim

Extension discovery begins only after the separate
[`fab7hq/ext-registry`](https://github.com/fab7hq/ext-registry) repository has a
reviewed, versioned `catalog.yaml` contract and Denim has published a compatible
release from [`fab7hq/denim`](https://github.com/fab7hq/denim).

The future `catalog.yaml` names immutable release artifacts and their digests,
Fab7 and host compatibility, executable names, declared capabilities, and
repository identity. The schema, supported YAML subset or parser, signing
policy, refresh URL, and release naming are entry-gate decisions for that later
phase. Fab7 must validate the entire candidate before atomically replacing
`~/.fab7/catalog.yaml`; an invalid refresh preserves the last-known-good file.

The future `fab7 ext install NAME --host HOST` flow will:

1. resolve one exact compatible registry entry;
2. show publisher, version, source, digest, capabilities, executable, and host
   mutation;
3. download and validate a prebuilt release in an operating-system temporary
   directory;
4. reject digest mismatch, path traversal, undeclared files, incompatible
   versions, executable collisions, and install hooks;
5. atomically install it beneath `~/.fab7/extensions/NAME/VERSION/`;
6. select its executable beneath `~/.fab7/bin/`;
7. register the release's host plugin through the native host CLI; and
8. return a finite result with one activation action.

An extension calls the stable `fab7` binary. It does not import Fab7 internals,
write proof records directly, or gain authority beyond the host's sandbox and
approval policy.

The target host-native journey is:

| Intent | Claude Code | Codex CLI |
|---|---|---|
| initialize Fab7 | `/fab7:init` | `$fab7:init` |
| list extensions | `/fab7:ext-list` | `$fab7:ext-list` |
| install Denim | `/fab7:ext-install denim` | `$fab7:ext-install denim` |
| start Denim | `/denim:start` | `$denim:start` |

These extension commands are target surfaces, not current Fab7 CLI claims.
Claude Code reload and Codex new-session behavior must be validated against the
then-current host versions during the extension phase.

## Acceptance boundaries

Fab7 onboarding closes independently when fresh disposable user state proves:

- deterministic executable bytes and preserved CLI exit codes;
- idempotent global installation and PATH mutation only after success;
- exact onboarding-state global and project layouts;
- atomic project initialization, record preservation, pinned-version repair,
  digest validation, and fail-closed dispatch; and
- native installation, discovery, and `/fab7:init` or `$fab7:init` execution in
  both supported hosts.

Extension distribution remains incomplete until later evidence proves:

- a closed `catalog.yaml` contract and last-known-good refresh behavior;
- verified Denim runtime and host-plugin installation;
- truthful reload or restart status before extension invocation;
- `/denim:start` and `$denim:start` reaching the installed Denim executable;
  and
- uninstall and interrupted-install recovery without damage to unrelated user,
  project, or host state.

## Deliberate exclusions

The onboarding phase supports macOS and Linux, Bash and Zsh startup files,
Python 3.11 or newer, Claude Code, and Codex CLI. It does not include Windows,
Fish, an extension registry implementation, Denim implementation, third-party
submission, ratings, ranking, catalog federation, dependency solving,
background updates, install hooks, cross-extension imports, private registries,
local extension copies, or unsupported-host compatibility shims.
