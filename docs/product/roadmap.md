---
title: Fab7 Product Roadmap
type: product
status: accepted
owner: product
last_updated: 2026-07-22
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
`$fab7:ext-list`, and `$fab7:ext-install`. Local source execution remains an
explicit human grant; the skill resolves and displays the source before asking
Fab7 to run the manifest-fixed bounded build.

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
federation, dependency solver, background updater, install hook, private
registry, cross-extension import contract, mutable source link, or
unsupported-host compatibility shim.
