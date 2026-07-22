---
title: Fab7 Extension Creator
type: plan
status: completed
implementation_authorized: true
publication_authorized: true
owner: product-and-engineering
last_updated: 2026-07-23
target_release: v0.2.2
authority_for:
  - extension developer onboarding
  - generic source scaffold boundary
  - implementation and release gates
depends_on:
  - docs/product/roadmap.md
  - docs/architecture/distribution.md
---

# Fab7 extension creator

## Outcome

A developer with Fab7 installed can open Claude Code or Codex in an existing
folder, invoke the native `ext-create` skill, and create one minimal Fab7
extension without reverse-engineering Muslin or copying native plugin trees.
The same deterministic entry point is also available directly:

```bash
fab7 ext create . --name example --publisher example
fab7 ext build . --host claude --host codex
```

`fab7 ext create` owns one generic host-neutral basic source scaffold. It writes
only a schema-2 manifest without `hosts`, an executable, canonical skill, and
standard-library test. `fab7 ext build --host` reads that source and uses only
the selected target adapters to build native roots plus a deterministic ZIP.
The existing `fab7 ext install --local` path remains the acceptance authority.
The shared host skill explains this sequence. During a Fab7 release build, the
builder injects local copies of the three authoritative architecture documents
for optional deeper context; the source tree keeps no second document copy,
scaffolder, or builder.

## Exclusions

This increment does not add language or framework selection, registry
submission, publication, Git hosting, CI generation, dependency solving,
mutable source links, or an extension runtime. It does not add Cursor or an
adapter for another unsupported host, generate a custom build script inside an
extension, or begin Denim.

## Implemented path

```text
/fab7:ext-create or $fab7:ext-create
    -> explain the source/build/install boundaries
    -> fab7 ext create <target> --name <name> --publisher <owner>
    -> optionally explain architecture when the developer asks
    -> obtain explicit approval before running generated code
    -> run the generated standard-library test
    -> fab7 ext build <target> --host <target-host> --json
    -> fab7 ext install --local <target> --host <host> --json
    -> fab7 ext doctor --json
    -> report the native reload or new-session action and start invocation
```

The generated source contains no host selection, plugin copies, package builder,
installer, or Fab7 import. Its executable observes Fab7 through
`fab7 --version`. The generated standard-library test invokes that source
executable with a bounded fake Fab7 binary; target-specific package behavior is
covered by Fab7's adapter and archive tests.

Fab7 has one canonical owner for `init`, `ext-list`, `ext-install`, and
`ext-create` instructions. A small `HostAdapter` contract with focused Claude
and Codex modules renders complete native layouts. A source script is
unnecessary: `install.sh` runs `core/fab7/release_build.py` as a source module,
which delegates plugin rendering to the same core assembler. No source
`scripts/` directory remains. Installed Fab7 and external schema-2 extensions
use `fab7 ext build` directly.

Muslin `0.1.1` proves the external creation boundary. Its worktree was cleared
and recreated directly with `fab7 ext create`; it now contains exactly the
generic manifest, canonical skill, executable, and generated unit test. It has
no private builder, copied plugin folders, README, CI, or other hand-authored
source. External verification calls
`fab7 ext build --host claude --host codex` for the package.

## Proof

- Focused creator, CLI, artifact, adapter, and package tests cover canonical
  identity, build-target selection, collision-safe failure, deterministic
  generated ZIPs, package validation, native skill output, and release-artifact
  inclusion.
- Artifact tests require one shared action owner, deterministic Claude and
  Codex rendering, build-injected byte-identical local copies of `overview.md`,
  `distribution.md`, and `ledger.md`, absence of source reference and host
  output trees, and absence of a scaffold script or templates inside the
  installed skill.
- Schema-1 local builds remain compatible; schema-2 builds use the public
  entrypoint and canonical skills contract.
- The complete deterministic Fab7 suite passes with `96` tests, and the release
  builder's drift check passes.
- A fresh isolated source installation registered Fab7 `0.2.2` in both native
  hosts. Direct `fab7 ext create` generated `thread-check`; its generated test,
  two-build comparison, local installation, diagnosis, and executable start all
  passed against installed Fab7 `0.2.2`.
- The recreated Muslin `0.1.1` source passed its generated test; two explicit
  Claude-and-Codex builds produced identical bytes and source digest
  `a664b5d87fd10219d625d2ef8332ea6a7299b7cf52e1bb06e1635f248394a1c1`.
  A fresh isolated Fab7 `0.2.2` installation activated that exact source in
  both hosts, passed diagnosis, and ran `muslin start` against Fab7 `0.2.2`.

Authenticated Claude Code and Codex sessions invoked the exact candidate's
`ext-create` skill in isolated repositories. Each created, tested, built, and
installed one host-specific fixture; a fresh second session invoked its
generated `start` skill and observed Fab7 `0.2.2`. The temporary integrations
were then removed. Hosted CI also passed for candidate commit
`153540e103a42f3fc8a47c65be5e6b8c9a6864fb` in
[run 29949097707](https://github.com/fab7hq/fab7/actions/runs/29949097707).

## Closure

The owner authorized publication on 2026-07-23, and the dependency-ordered
release completed:

1. [Fab7 `v0.2.2`](https://github.com/fab7hq/fab7/releases/tag/v0.2.2) with its
   source-archive checksum asset;
2. [Muslin `v0.1.1`](https://github.com/fab7hq/muslin/releases/tag/v0.1.1) with
   deterministic package digest
   `f578596486444f776f39bf9616ca549d22df62328c72fd394a8aec852e3f0285`;
3. [ext-registry `v0.1.1`](https://github.com/fab7hq/ext-registry/releases/tag/v0.1.1)
   with the digest-pinned Muslin entry and passing hosted CI; and
4. a fresh network installation from the immutable Fab7 installer, followed by
   registry refresh, Muslin installation into Claude and Codex, healthy
   diagnosis, native plugin discovery, and `muslin start` observing Fab7
   `0.2.2`.

The extension creator increment is released and complete. Linux installation
was not independently observed; this does not widen the macOS evidence.
