---
title: Fab7 Product Roadmap
type: product
status: accepted
owner: product
last_updated: 2026-07-25
authority_for:
  - completed product capability
  - current exclusions
  - accepted next delivery outcome
  - deferred extension products
---

# Fab7 product roadmap

## Lean proof baseline — complete

Fab7 has one dependency-free proof path: initialize `.fab7/records/`, append a
closed claim or executed-evidence record, bind evidence to the tested Git
commit and output digest, and fail readiness when the latest claim lacks fresh
passing evidence. `audit`, `doctor`, the CLI, and the small composite action use
the same deterministic contract.

Fab7 still does not model plans, approval, arbitrary events, methodology, or
agent prose as proof.

## Fab7 onboarding — released and owner-accepted

Release `v0.1.0` established the user and project path:

```text
install.sh
    -> verified immutable Fab7 beneath ~/.fab7/
    -> ~/.fab7/bin on the user's PATH

fab7 install claude|codex
    -> release-bundled Fab7 plugin through the native host CLI

/fab7:init or $fab7:init
    -> tracked .fab7/project.json and .fab7/.gitignore
    -> ignored, digest-verified .fab7/bin/fab7
    -> preserved .fab7/records/
```

The owner accepted source and network onboarding on 2026-07-20. Historical
evidence limits—unretained exact transcripts and incomplete independent Linux
and Codex observations—remain in the
[`onboarding plan`](../plans/onboarding.md#closure).

## Fab7 extension distribution — released and complete

Release `v0.2.0` adds one lean extension path without loading
extensions into the proof core:

- refresh and list the closed `fab7hq/ext-registry` catalog while preserving a
  validated last-known-good copy and its Git blob/content identity;
- install an exact reviewed registry release or one explicitly approved local
  source tree through the same closed package validator;
- keep all extension bytes in immutable user-global snapshots beneath
  `~/.fab7/extensions/` and expose only a stable executable selector;
- activate complete package-bundled Claude Code and Codex plugins through their
  native CLIs;
- report registry or local origin, selected version, install identity, and
  active hosts;
- diagnose the catalog plus selected and inactive installed snapshots; and
- uninstall one host at a time, deleting the extension only after its final
  integration is removed.

The thin host surfaces are `/fab7:ext-list`, `/fab7:ext-install`,
`$fab7:ext-list`, and `$fab7:ext-install`. Local source installation remains an
explicit human grant; the skill resolves and displays the source before asking
Fab7 to assemble its bounded discovered files.

[`fab7hq/muslin`](https://github.com/fab7hq/muslin) is the minimal closure
fixture. Its only runtime behavior is `muslin start`, which calls the public
`fab7 --version` binary. It is not a product workflow and adds no shared state.
Its reproducible `0.1.0` ZIP has SHA-256
`4b105587a409d275fdf2a1712db6706a093ec0ad6fcfa42d6c7c022fcd93f9a1`.

On 2026-07-22 both the source lane and the immutable network release passed in
fresh isolated macOS homes with Claude Code `2.1.217` and Codex CLI `0.144.6`.
Both hosts discovered Muslin, `muslin start` observed Fab7 `0.2.0`, diagnosis
passed, partial uninstall preserved the other host, and final uninstall removed
only Muslin state.

### Closure

The owner authorized publication, and the release sequence completed in
dependency order:

1. Fab7 `v0.2.0` and its source checksum asset;
2. Muslin `v0.1.0` and its exact deterministic ZIP;
3. `ext-registry` `v0.1.0` with one digest-pinned Muslin entry and CI against
   released Fab7 `v0.2.0`; and
4. the fresh network lifecycle described above.

The [`extension closure plan`](../plans/ext-registry.md) owns exact proof and
residual limits. [`status.yaml`](../status.yaml) records Fab7 closure as
completed.

### Marketplace migration maintenance — released and complete

Release `v0.2.1` fixes the upgrade collision exposed after
`v0.2.0`: installing Fab7 or an extension at a different version now migrates
an older marketplace only when both roots are provably in the same managed
Fab7 family. The operation removes and recreates the native host registration,
verifies the new plugin, and rolls back to the prior plugin on failure.
Unrelated same-name marketplaces still fail closed, and one host command still
cannot migrate another active extension host implicitly.

The [`marketplace migration plan`](../plans/marketplace-migration.md) owns the
completed release and network proof. [`status.yaml`](../status.yaml) records
the maintenance phase as completed.

## Extension developer onboarding — released, source contract superseded

Release `v0.2.2` adds `fab7 ext create` plus the thin
`/fab7:ext-create` and `$fab7:ext-create` host skills. From any existing
non-symlink folder, the explicit user invocation:

- resolves a canonical extension identity;
- renders one generic basic source scaffold without overwriting existing files;
- creates one host-neutral manifest, one executable source, one canonical
  skill, and one standard-library test;
- delegates target selection, native plugin generation, and deterministic ZIP
  assembly to the public `fab7 ext build --host` command and shared adapters;
- explains that the executable crosses the Fab7 boundary only through the
  public binary;
- offers a bundled, optional architecture walkthrough that maps the generated
  files to Fab7 core, distribution, lifecycle, proof, and human authority; and
- obtains human approval before running generated code or delegating to
  `fab7 ext install --local` and `fab7 ext doctor`.

The release also replaces the duplicated Claude and Codex copies of `init`,
`ext-list`, `ext-install`, and `ext-create` with canonical action sources and
focused Claude/Codex build adapters. The same assembler powers Fab7's release
plugin roots and extension packages. The creator adds no second
validator or plugin builder. Registry publication, language selection, Git
hosting, CI generation, unsupported-host adapters, and extension release
automation remain excluded. Muslin `v0.1.1` and ext-registry `v0.1.1` were
released after Fab7, and a fresh network installation passed in both supported
hosts.

Muslin `v0.1.1` is the released creator fixture. Its worktree was rebuilt from
generic `fab7 ext create` output and contains only the manifest, canonical
skill, executable, and generated test. Two
`fab7 ext build --host claude --host codex` runs proved deterministic target
package output before publication.

Hosted CI, authenticated `/fab7:ext-create` and `$fab7:ext-create` model
invocations, immutable Fab7 installation, network registry refresh, and Muslin
installation passed. The
[`extension creator plan`](../plans/ext-create.md) owns the exact closure proof
and residual limit.

## Single schema-1 extension source — superseded before publication

The `v0.3.0` candidate deliberately replaces every earlier extension source,
package, receipt, and catalog shape. There is no backward-compatible parser or
migration mode. An extension author now maintains exactly:

```json
{
  "name": "example",
  "publisher": "example",
  "schema": 1,
  "version": "0.1.0"
}
```

`src/extension.py` is always the entrypoint. Fab7 automatically discovers all
bounded regular files under `src/`, `tests/`, and `skills/`: source modules are
shipped in one deterministic Python executable archive, tests affect source
identity without being shipped or run, and direct skill directories are
rendered with their adjacent files. Authors no longer list files, configure
the entrypoint, declare capabilities, or maintain Fab7 minimum/maximum ranges.
Fab7 generates `fab7_api: 1` in the closed package, receipt, and catalog
contracts.

That implementation used only the Python standard library. It was not
published before the dependency and native-build need was accepted, so
`v0.4.0` supersedes its zipapp package path without a compatibility release.

Local deterministic verification is complete. Muslin `0.2.0` has been
recreated under the reset contract and its multi-file source, deterministic
package, both-host local installation, diagnosis, execution, and uninstall
have passed. Publication is not complete: ext-registry must be updated, hosted
CI must pass, immutable artifacts must be released in dependency order, and
fresh network plus authenticated Claude and Codex journeys must be observed.
The [`extension source reset plan`](../plans/extension-source-reset.md) owns
those gates.

## uv-managed native distribution — released and complete

The accepted `v0.4.0` path requires host uv, recommends tested version
`0.11.29` without enforcing it, installs Fab7-owned standard CPython `3.14.6`,
and uses PyInstaller `6.21.0` only inside fresh build environments. Fab7 and
extensions become self-contained native executables. The managed interpreter
and one concurrency-safe uv cache are shared; builder venvs and extension
dependency roots are never shared or installed.

Every extension keeps the four-field schema-1 manifest and canonical
`src/extension.py`, while mandatory `pyproject.toml` and `uv.lock` own sorted
public-PyPI dependencies and their hashes. Registry entries now identify
immutable source bundles. Registry and explicitly approved local source use
the same target-local builder, package identity, immutable snapshot, host
activation, rollback, diagnosis, and uninstall path.

Local Apple Silicon implementation proof has passed for exact Python
bootstrap, byte-identical native Fab7 and extension builds, a multi-file
PyYAML extension, generated uv projects, source-registry convergence,
dependency-free installed snapshots, concurrent conflicting dependency
builds, installer rollback, non-recommended uv acceptance, and all `108`
deterministic tests. The real sibling Muslin source was also removed and
recreated as a fresh `0.2.0` uv project using native Fab7 `0.4.0`; root commit
`b73f43708bfd52c76c8ba93de7a83ac0d7606d09` owns its locked PyYAML helper.
Byte-identical native packages and the local lifecycle in both real host CLIs
passed.

Fab7 commit `f323c2155f39c3113dc72a36bcf5239a8baa17f6` and Muslin root
commit `b73f43708bfd52c76c8ba93de7a83ac0d7606d09` are now on public `main`.
Hosted macOS/Linux CI passed. Fresh GitHub clones also passed native Fab7
installation and both-host Muslin installation, discovery, execution,
diagnosis, and idempotence in an isolated home.

Fab7 `v0.4.0`, Muslin `v0.2.0`, and ext-registry catalog `0.2.0` are released.
A fresh isolated home passed immutable Fab7 installation, catalog refresh,
Muslin registry installation into both hosts, diagnosis, execution, native
host discovery, and idempotence. Authenticated model invocation was not
performed and remains a recorded residual rather than release evidence. The
[`uv migration plan`](../plans/uv-migration.md) owns the complete contract and
stop condition.

## Denim — deferred

[`fab7hq/denim`](https://github.com/fab7hq/denim) remains the first product
extension, but it is not part of Fab7 closure. Denim will own its product
runtime, manifest, host plugins, artifacts, checksums, and tests and will call
Fab7 only through public commands. Its requirements and implementation need a
separate authorization.

## Still excluded

There is no generic record framework, extension runtime in core, methodology,
planning or orchestration layer, configurable policy engine, provider registry,
service, daemon, dashboard, third-party submission workflow, catalog
federation, private dependency index, sdist build, background updater, install
hook, cross-extension import contract, mutable source link, persistent
extension venv, remote builder, cross-compilation, or unsupported-host
compatibility shim.
