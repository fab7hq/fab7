---
title: Fab7 Onboarding and Extension Distribution
type: architecture
status: accepted
implementation_status: implemented
owner: architecture
last_updated: 2026-07-25
authority_for:
  - repository ownership
  - user-global and project-local filesystem layouts
  - Fab7 bootstrap installation
  - agentic CLI plugin registration
  - extension catalog, package, installation, and lifecycle contracts
---

# Fab7 onboarding and extension distribution

Fab7 has one user-global distribution plane around its dependency-free proof
core. It installs Fab7, registers thin host plugins, pins Fab7 per project,
creates generic extension source, and installs extensions from either
the reviewed catalog or one explicitly approved local source tree. Extensions
remain external programs and call Fab7 only through its public binary.

The onboarding path is released and owner-accepted at `v0.1.0`. Extension
distribution is released at `v0.2.0`; its immutable network-registry lifecycle
was observed before closure. Release `v0.2.1` adds ownership-aware marketplace
migration. Release `v0.2.2` adds `fab7 ext create` and shared Claude/Codex
creator skills. The checkout now implements the breaking `v0.4.0` uv and
native-build migration over the unpublished schema-1 reset. Fab7 `v0.4.0`,
Muslin `v0.2.0`, and ext-registry catalog `0.2.0` are released.

## Contents

- Repository ownership
- User-global and project-local layouts
- Current commands and host plugin build
- Bootstrap and host registration
- Catalog, source, package, and runtime contracts
- Installation, lifecycle, and extension authoring
- Evidence, exclusions, and release boundary

## Repository ownership

| Repository | Current state | Owns |
|---|---|---|
| [`fab7hq/fab7`](https://github.com/fab7hq/fab7) | released `v0.4.0` | proof core, pinned native builder, installer, CLI, host plugins, generic extension creator, catalog validator, and extension installer |
| [`fab7hq/ext-registry`](https://github.com/fab7hq/ext-registry) | catalog `0.2.0` on `main` | one reviewed `catalog.yaml` and CI pinned to released Fab7; no extension source or artifacts |
| [`fab7hq/muslin`](https://github.com/fab7hq/muslin) | released `v0.2.0` | deterministic closure fixture, canonical skill, source-bundle asset, and tests |
| [`fab7hq/denim`](https://github.com/fab7hq/denim) | deferred | first product extension when separately authorized |

Muslin is proof infrastructure, not the first product extension. The registry
never vendors extension bytes. Each extension repository publishes its own
immutable package and checksum.

## User-global layout

Fab7 creates paths only when their owning operation first needs them:

```text
~/.fab7/
├── .extension.lock
├── cache/uv/
├── toolchains/python/
├── builds/
├── bin/
│   ├── fab7 -> ../runtime/<selected-version>/bin/fab7
│   └── <extension> -> ../extensions/<name>/<install-id>/bin/<name>
├── runtime/
│   └── <fab7-version>/
│       ├── manifest.json
│       ├── bin/fab7
│       └── hosts/{claude,codex}/
├── catalog.yaml
├── catalog.lock.json
└── extensions/
    └── <name>/
        └── <install-id>/
            ├── manifest.json
            ├── bin/<name>
            └── hosts/{declared-host}/
```

| Path | Intention |
|---|---|
| `bin/` | Stable selectors placed on `PATH`; never implementation source. |
| `cache/uv/` | Shared concurrency-safe uv cache; never installed dependency state. |
| `toolchains/python/` | Fab7-owned standard CPython 3.14.6. |
| `builds/` | Fresh task roots; successful operations remove their task directory. |
| `runtime/<version>/` | Immutable installed native Fab7 release, including the two complete host marketplace roots. |
| `catalog.yaml` | Last-known-good, fully validated registry content. |
| `catalog.lock.json` | Registry, branch, Git blob SHA, and catalog content digest observed during refresh. |
| `extensions/<name>/<install-id>/` | Immutable target/toolchain-bound native extension snapshot. Registry IDs are `<version>-<package-digest>`; local IDs are `dev-<package-digest>`. |
| `manifest.json` | Closed installation receipt: identity, compatibility, file digests and modes, origin, supported hosts, and active host integrations. |
| `.extension.lock` | Empty lock file. The operating-system lock exists only during catalog or extension mutation and is released on process exit. |

No secrets, raw host transcripts, mutable source links, copied host
configuration, persistent staging tree, or second receipt store belongs here.

## Project-local layout

`fab7 init` creates the project pin and ignored executable; extensions remain
user-global:

```text
<repo>/.fab7/
├── project.json          # tracked Fab7 version and executable digest
├── .gitignore            # tracked; exactly /bin/
├── records/              # tracked append-only claim/evidence ledgers
└── bin/fab7              # ignored copy of the pinned executable
```

There is no project-local extension store, catalog, cache, marketplace, or
receipt. An extension reaches the project-pinned Fab7 executable through the
stable `fab7` dispatcher when a project command is invoked.

## Current commands

All distribution commands run from the selected global executable:

```text
fab7 install claude|codex
fab7 init
fab7 ext refresh
fab7 ext list [--refresh] [--catalog PATH]
fab7 ext create [TARGET] --name NAME --publisher OWNER
fab7 ext build [SOURCE] --host HOST [...] [--output ZIP]
fab7 ext install NAME --host claude|codex [--catalog PATH]
fab7 ext install --local PATH --host claude|codex
fab7 ext doctor
fab7 ext uninstall NAME --host claude|codex
```

Project proof commands still validate `.fab7/project.json` and dispatch to the
pinned `.fab7/bin/fab7`. Extension commands do not dispatch into a project and
do not alter proof records.

The released host surfaces are `/fab7:init`, `/fab7:ext-list`,
`/fab7:ext-install`, and `/fab7:ext-create` in Claude Code and the corresponding
`$fab7:*` skills in Codex. Claude requires `/reload-plugins`; Codex loads new
skills in a new session. Host files delegate runtime state changes to the CLI.

## Host plugin source and build

Shared host behavior has one reviewed source:

```text
plugins/fab7/
└── actions/
    ├── ext-create/SKILL.md.tmpl
    └── {init,ext-list,ext-install}/SKILL.md.tmpl

docs/architecture/
└── {overview,distribution,ledger}.md
```

`core/fab7/plugin/adapter.py` defines one build-time adapter contract. The
focused `claude_adapter.py` and `codex_adapter.py` implementations own only the real
differences: invocation prefix, command or skill destination, frontmatter,
manifest, and marketplace shape. `build.py` owns shared deterministic assembly
and Fab7's action composition. During a Fab7 release build it injects the three
canonical architecture documents directly into each generated `ext-create`
skill; there is no checked-in reference mirror or source `plugins/fab7/hosts`
tree. `core/fab7/release_build.py` includes the executable, built-in source
template, and complete host roots in a release.
`install.sh` executes that source module directly during bootstrap; no source
`scripts/` directory remains. The release digest covers every adapter,
template, action, and reference input.

This is build-time adaptation, not a runtime plugin abstraction. Fab7 and its
extensions can call the same assembler, while installed extensions still see
closed native host roots. Cursor or another host receives no placeholder
adapter, manifest, CLI choice, or compatibility claim until its complete
native build, validation, installation, activation, rollback, and uninstall
path is implemented and observed.

## Bootstrap and host registration

`install.sh` supports macOS and Linux with Bash or Zsh, Git, and a valid host
uv. It does not install or upgrade uv and requires no system Python. Missing
or malformed uv fails before Fab7-owned mutation. Version `0.11.29` is the
tested recommendation; another valid version produces an advisory and
continues. The installer verifies an immutable tagged source archive against
its release checksum, uses uv to install standard GIL-enabled CPython 3.14.6
beneath `FAB7_HOME`, creates a fresh builder, installs the hash-locked
PyInstaller 6.21.0 toolchain, and builds a deterministic native executable. It
installs the closed release under
`runtime/<version>/`, atomically selects it, and then adds one idempotent PATH
block to the chosen shell profile. `--source PATH` is the reviewed-checkout
lane used for development and release validation. Python installation disables
uv's user-level executable shim, so no managed-Python path is written outside
`FAB7_HOME`.

The host uv executable, managed CPython, and `cache/uv` are the only shared
build inputs. Fab7's release and each extension build use a fresh venv and
dependency root. Ambient venv, Python path, uv/pip index configuration, and
user packages are removed from the build environment. Installed Fab7 and
extension snapshots contain no venv, dependency tree, cache, or source
checkout.

`fab7 install claude|codex` validates the release-bundled marketplace root,
uses literal bounded native host commands, verifies plugin discovery, and
reports the required reload or restart action. If the same name points to an
older root in the exact selected `FAB7_HOME/runtime` family, Fab7 validates the
surviving old artifacts, replaces the registration through the host CLI, and
reports `migrated`. Another home, invalid old root, or unrelated source remains
a marketplace conflict. A failed replacement restores and verifies the prior
registration or reports an explicit rollback failure.

## Catalog contract and refresh

`catalog.yaml` is JSON-compatible YAML v1, parsed with the Python standard
library and duplicate-key rejection. Its root is exactly `schema`, `registry`,
`catalog_version`, and canonical `extensions`. Each entry is closed over:

```text
name, publisher, version, fab7_api, hosts, source
```

The source is an exact GitHub `releases/download/vVERSION/` source-bundle asset
plus its SHA-256 digest. `fab7_api` is exactly `1`. Entries and list values are
sorted and unique. Unknown fields, moving release URLs, another API, or
noncanonical identity fail closed.

Refresh reads only `fab7hq/ext-registry` through GitHub's contents API at
`main`. Fab7 validates the response's file type, Base64 bytes, size, and Git
blob SHA, then validates the complete catalog. It rejects a lower catalog
version and rejects conflicting bytes at the same version. Only a valid
candidate atomically replaces the last-known-good catalog and lock record.

## One native builder, two source origins

A registry install downloads the catalog-selected source bundle, verifies its
digest, and extracts only bounded Unix regular files. A local install reads the
same source tree directly after explicit approval. Both enter the identical
validator and native builder.

The validator reads the four-field `fab7-extension.json`, closed
`pyproject.toml`, current `uv.lock`, and bounded regular files beneath `src/`,
`tests/`, and `skills/`. It accepts only schema `1`; there is no legacy parser,
zipapp, or compatibility lane. The canonical entrypoint is always
`src/extension.py`. `pyproject.toml` must match source name/version, require
`==3.14.*`, and keep sorted runtime dependencies in
`[project].dependencies`. `uv.lock` must resolve those dependencies from only
the public PyPI registry and provide wheel hashes. Workspaces, editables, local
or VCS paths, direct URLs, private or alternate indexes, and sdists fail
closed.

Every discovered `src/` file and the locally materialized locked-wheel root
enter one current-platform PyInstaller executable. Every discovered `tests/`
file affects source identity but is neither shipped nor run by build. Each
direct `skills/<name>/` directory must contain `SKILL.md`; Fab7 renders it and
copies its adjacent files into the selected native host roots. Generated
Python caches, `.venv`, and `dist` trees are ignored. Symlinks, unsupported
paths, empty required trees, `src/__main__.py`, stale locks, and sources outside
the 512-file or 32 MiB limits fail closed.

The source manifest is exactly:

```json
{
  "name": "example",
  "publisher": "example",
  "schema": 1,
  "version": "0.1.0"
}
```

Authors do not list files, choose an entrypoint, declare capabilities, select
hosts, state Fab7 version ranges, or choose PyInstaller. An explicit host list
tells Fab7's built-in adapters which native roots to create. PyInstaller
analysis and hooks execute during a build, so direct invocation or explicit
host-skill approval is required after disclosing dependency downloads, current
native target, and hook execution.

`fab7 ext build [SOURCE] --host HOST [...] [--output ZIP]` exposes that exact
build path without installation. It requires one or more unique supported
host roots, defaults to the current folder and
`dist/<name>-<version>-<native-target>-<host[-host...]>.zip`, refuses to replace
an existing output, emits a deterministic current-platform ZIP, and reports
the native target, host list, source, lock, toolchain, and package SHA-256
digests. Local installation reuses the same schema parser and package builder;
it supplies the complete built-in target set so one source digest retains a
stable multi-host development snapshot, then activates only the requested
host. It does not maintain another bundling contract.

Both origins then use the same schema-1 `extension.json` package contract:

- exact fields `schema`, `name`, `publisher`, `version`, `fab7_api`, `hosts`,
  `build`, and `files`, with generated `fab7_api: 1`;
- a closed build identity covering source, lock export, dependency root,
  native target, Fab7 toolchain, and executable digests;
- one executable at `bin/<name>` with mode `0755`;
- an optional root `LICENSE` and all host files at mode `0644`, with host files
  contained beneath declared host roots;
- exact SHA-256 digest for every installed file;
- complete contained Claude and/or Codex marketplace roots whose source points
  only to `./plugins/<name>`; and
- no symlinks, traversal, undeclared files or hosts, install hooks, imports
  into Fab7, or executable collisions.

Fab7 materializes an immutable installation, atomically selects its executable,
registers the requested host plugin, and only then records that integration.
Failures restore the prior selector and host registration or return an explicit
rollback failure.

Reinstalling unchanged source, target, and toolchain is idempotent. A changed
source, lock, target, toolchain, dependency root, or executable produces a new
package-digest-bound snapshot. If the requested host is the sole active integration,
Fab7 migrates it and keeps the prior snapshot as an inactive rollback copy. If
another host is active, Fab7 rejects implicit migration; the user must
explicitly uninstall those host integrations before selecting changed bytes.
Only the selected snapshot may claim active integrations, and `ext doctor`
validates selected and inactive snapshots.

The host registration layer applies the same ownership rule to an extension:
only roots beneath the exact `FAB7_HOME/extensions/<name>` family may replace
one another. It never treats a matching marketplace name alone as ownership.

Uninstall first removes only the named host integration. The executable and
package remain while another host is active. Removing the final host deletes
the selector and all snapshots for that extension. It never removes unrelated
Fab7 releases, extensions, host state, or project data.

## Extension authoring surface

`fab7 ext create` is the deterministic host-neutral authoring boundary. It takes
an existing target, canonical name and publisher, and extension version. It
preflights the complete built-in `basic` template and refuses any collision
before writing. The schema-1 source has the exact four-field manifest, minimal
closed `pyproject.toml`, generated `uv.lock`, canonical `src/extension.py`, one
`start` skill, and one standard-library test. Creation is transactional across
template writes and locking. It contains no packaging script, persistent venv,
or native host manifest. Authors may add public-PyPI runtime dependencies,
ordinary packages and modules beneath `src/`, tests beneath `tests/`, and
additional canonical skill directories without editing the manifest.

The shared `/fab7:ext-create` and `$fab7:ext-create` skills keep creation
task-first: infer safe identity, call the CLI, explain the generated source and
locked dependency boundary, and obtain approval before isolated test, build,
or installation. The release builder
injects byte-identical local copies of the three authoritative architecture
documents—`overview.md`, `distribution.md`, and `ledger.md`—into the generated
skill. They load only when their specific deeper context is requested, so
installed skills do not need GitHub access to explain Fab7's contracts.

The creator does not initialize Git, create remotes, publish, generate CI, pick
a host, or overwrite user work. `fab7 ext build --host` remains the only native
plugin and ZIP assembler and owns target selection; `fab7 ext install --local`
remains installation authority.

## Implemented and released evidence

The deterministic suite covers catalog closure and last-known-good refresh,
source and package bounds, archive traversal, digest and compatibility checks,
immutable snapshots, host migration and rollback, mutation locking, diagnosis,
multi-host uninstall, CLI routing, artifact contents, and native host command
shapes.

On 2026-07-22 a fresh isolated macOS home observed Fab7 `0.2.0` source
installation, Fab7 plugin discovery, local Muslin installation in Claude Code
`2.1.217` and Codex CLI `0.144.6`, `muslin start` observing `fab7 0.2.0`, healthy
diagnosis, partial host uninstall, and bounded final removal. Muslin's two
independent ZIP builds matched SHA-256
`4b105587a409d275fdf2a1712db6706a093ec0ad6fcfa42d6c7c022fcd93f9a1`.

The owner authorized release on 2026-07-22. Fab7 `v0.2.0`, Muslin `v0.1.0`,
and ext-registry `v0.1.0` were published in dependency order. Their hosted CI
passed. A second fresh isolated macOS home then installed Fab7 from the exact
tag, refreshed the network catalog, installed Muslin by registry name into both
hosts, verified its receipt and public-binary invocation, preserved the Codex
integration during Claude uninstall, and removed only Muslin state after final
uninstall.

No authenticated model invocation of the host-native commands was performed;
the host CLIs' plugin discovery was observed directly. Linux extension
installation was not independently observed.

For release `v0.2.2`, focused tests and a fresh isolated macOS home proved
generic host-neutral creation, collision rejection, deterministic
target-specific package output, release inclusion of template assets, and
shared skill discovery in Claude Code `2.1.217` and Codex CLI `0.145.0`.
Authenticated sessions in both hosts invoked the creator and a generated
extension's start skill. Muslin `v0.1.1` was cleared and recreated from
`fab7 ext create` alone, then released with a deterministic Claude-and-Codex
package. A final fresh home installed Fab7 from the immutable `v0.2.2` tag,
refreshed ext-registry `v0.1.1`, installed Muslin by registry name into both
hosts, passed diagnosis, and ran it against Fab7 `0.2.2`.

The `v0.3.0` candidate replaces that extension source and artifact contract
without backward compatibility. Local deterministic tests prove the four-field
schema, canonical entrypoint, recursive module execution, automatic test
hashing without shipment, adjacent skill-file copying, cache exclusion,
source bounds, simplified catalog/package/receipt closure, and byte-stable
archives. Muslin integration evidence follows; ext-registry, hosted CI,
immutable release artifacts, and fresh network or authenticated Claude/Codex
journeys still require separate proof.

Muslin `0.2.0` has since been recreated locally by Fab7 `0.3.0` with
`src/extension.py` importing `src/helper.py`. Two packages matched byte for
byte; the executable contained both modules. Real Claude Code `2.1.217` and
Codex CLI `0.145.0` installed the snapshot in a disposable home, diagnosis and
execution passed, partial uninstall preserved the remaining host, and final
uninstall removed it. Ext-registry, hosted CI, immutable release artifacts,
authenticated model invocation, and network installation remain unproved.

The `v0.4.0` implementation supersedes that unpublished package path.
On 2026-07-24, sandboxed `uv 0.11.29` installed standard CPython `3.14.6`;
PyInstaller `6.21.0` produced byte-identical Fab7 binaries and byte-identical
extension packages from fresh builders. The real sibling Muslin source was
removed from its active path and recreated as a fresh `0.2.0` repository by
native Fab7 `0.4.0`; root commit
`b73f43708bfd52c76c8ba93de7a83ac0d7606d09` owns the reset source. Its
canonical `src/extension.py` imports
`src/helper.py`; its uv project locks PyYAML `6.0.3`. Two native packages were
byte-identical with SHA-256
`7cdfa957b276de1ce741c5064e7110afcbc05c15c85ea57241fd6ceed2b00b6a`, and
the executable ran against native Fab7 `0.4.0` with the bundled dependency.
Real Claude and Codex CLIs passed isolated local installation, diagnosis,
execution, partial uninstall, and final removal.

Deterministic tests cover the new source, package, receipt, catalog, rollback,
and required-but-version-advisory uv contracts. Fab7 commit
`f323c2155f39c3113dc72a36bcf5239a8baa17f6` and Muslin root commit
`b73f43708bfd52c76c8ba93de7a83ac0d7606d09` are on their public `main`
branches. Hosted macOS/Linux CI passed, as did a fresh isolated clone and
reviewed-source installation of Fab7 followed by both-host local-source
installation, native execution, diagnosis, host discovery, and idempotence for
Muslin. The network-built extension package SHA-256 was
`321ae560e09887fc639feb7a29d0f25814bae4f95e871db12e221e0c42d67757`.

Fab7 `v0.4.0`, Muslin `v0.2.0`, and ext-registry catalog `0.2.0` were then
published. A fresh isolated home passed release-checksum Fab7 installation,
registry refresh, Muslin download and native build, both-host integration,
diagnosis, execution, discovery, and idempotence. The registry-built package
SHA-256 was
`f8ec1b798f78abb4fa847d43eedbc386b1ccab582db35e840dce84877e940b72`.
Authenticated Claude/Codex model journeys remain unperformed; native host
discovery was observed directly. The complete local suite passed `108` tests,
including fresh-home installer rollback, non-recommended uv acceptance, and
concurrent extensions with conflicting dependency versions sharing only the
managed Python and uv cache.

## Exclusions

Fab7 still has no extension runtime in core, catalog federation, private or
alternate dependency index, sdist builder, VCS/path/editable dependency,
cross-compiler, remote builder, ranking, ratings, background updater, install
hook, cross-extension import contract, mutable development link, persistent
runtime venv, service, daemon, dashboard, or compatibility shim. Denim remains
a separate future product decision.
