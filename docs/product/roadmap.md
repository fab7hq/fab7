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

## Fab7 extension distribution — implementation complete, release pending

The `0.2.0` release candidate adds one lean extension path without loading
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

On 2026-07-22 the source lane passed in a fresh isolated macOS home with Claude
Code `2.1.217` and Codex CLI `0.144.6`: both hosts discovered Muslin,
`muslin start` observed Fab7 `0.2.0`, diagnosis passed, partial uninstall
preserved the other host, and final uninstall removed only Muslin state.

### Release boundary

Fab7 is not closed merely because source implementation passed. The remaining
human-controlled sequence is:

1. publish Fab7 `v0.2.0` and its checksum asset;
2. publish Muslin `v0.1.0` and its exact ZIP;
3. publish `ext-registry` with one Muslin entry and its prepared CI pinned to
   released Fab7 `v0.2.0`; and
4. observe a fresh network catalog refresh, registry-name install, invocation,
   diagnosis, partial uninstall, and final removal.

The [`extension closure plan`](../plans/ext-registry.md) owns exact proof and
stop rules. [`status.yaml`](../status.yaml) remains `ready_for_release` until
the network observation passes or the owner explicitly accepts a recorded
limit.

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
