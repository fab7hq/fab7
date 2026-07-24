---
title: Fab7 Extension Source Reset
type: plan
status: implemented
implementation_authorized: true
publication_authorized: false
owner: product-and-engineering
last_updated: 2026-07-24
target_release: v0.3.0
authority_for:
  - current extension source contract
  - automatic source discovery
  - simplified package and catalog identity
  - implementation and release gates
depends_on:
  - docs/product/roadmap.md
  - docs/architecture/distribution.md
---

# Fab7 extension source reset

## Outcome

An extension author maintains one four-field `fab7-extension.json`, one
canonical `src/extension.py`, normal source and test trees, and canonical skill
directories. Fab7 discovers the complete bounded source closure, builds one
deterministic executable Python archive, renders the selected native hosts, and
uses the existing immutable installation lifecycle.

```json
{
  "name": "example",
  "publisher": "example",
  "schema": 1,
  "version": "0.1.0"
}
```

This is a breaking reset. Fab7 accepts only this schema-1 source shape and the
matching schema-1 catalog, package, and receipt shapes. It does not retain the
retired custom build command, declared file list, configurable entrypoint,
capabilities, Fab7 minimum/maximum range, or another compatibility path.

## Fixed contract

The source layout is:

```text
fab7-extension.json
src/
└── extension.py
tests/
└── ...
skills/
└── <name>/
    ├── SKILL.md
    └── ...
LICENSE                         # optional
```

Fab7 discovers every bounded regular file beneath `src/`, `tests/`, and
`skills/` in canonical order. It ignores generated Python caches, rejects
symlinks and unsupported paths, and applies the existing 512-file and 32 MiB
source limits. `src/` becomes the executable archive; `tests/` contributes to
the source digest but is neither shipped nor executed by build; each direct
`skills/<name>/SKILL.md` is a host action and its adjacent files are copied
with it. An optional root `LICENSE` is retained.

The package, receipt, and catalog use generated `fab7_api: 1` compatibility.
Authors do not declare it. Package identity is exactly name, publisher,
version, Fab7 API, and selected hosts. The executable path is derived as
`bin/<name>` and the repository as
`https://github.com/<publisher>/<name>`.

## Authority and exclusions

`fab7 ext build` reads and packages bytes but does not execute extension-owned
code. Tests still require explicit human approval and a separate command.
`fab7 ext install --local` remains installation authority. This increment adds
no `uv` runtime dependency, dependency solver, virtual environment, arbitrary
build hook, native dependency support, registry publication, host adapter, or
mutable source link.

## Implementation

- Replace local-source parsing with the four-field schema and bounded recursive
  discovery.
- Extract the existing standard-library deterministic Python archive assembly
  and reuse it for Fab7 and extension executables.
- Remove the retired subprocess build path and its timeout/output machinery.
- Generate package and host metadata from source identity, selected hosts,
  canonical skills, and `fab7_api`.
- Keep source, package, scaffold, catalog, and installation code beneath the
  `core/fab7/extension/` namespace; let `plugin/` own only native host
  rendering.
- Simplify catalog, package, receipt, scaffold, and host guidance together.
- Recreate Muslin with the reset contract, then update the registry entry
  before publication.

## Proof and stop condition

Implementation is ready only when:

- focused tests prove minimal manifests, recursive module execution, automatic
  test hashing without test shipment, skill-reference copying, cache exclusion,
  source bounds, symlink rejection, deterministic archives, and simplified
  catalog/package/receipt validation;
- the complete deterministic test suite passes;
- the release build is byte-stable and executable outside the checkout;
- shell syntax, Python compilation, documentation links/status syntax, and
  `git diff --check` pass; and
- remaining external work is stated truthfully.

Publication remains a separate owner decision. Before release, the Muslin
candidate and ext-registry entry, hosted CI, immutable installer/checksum
artifacts, and fresh Claude/Codex network journeys must use the reset contract.

## Current evidence

The final local tree passed `54` focused extension/catalog/artifact tests and
the complete `96`-test deterministic suite on 2026-07-24. The release builder
produced byte-identical trees; the suite executed the generated archive outside
the checkout. A clean virtual environment installed the built `0.3.0` wheel,
created a schema-1 source, and built its Codex package. Python source
compilation, installer shell syntax, documentation links, status syntax, and
diff hygiene passed.

Muslin `0.2.0` was then cleared to its Git boundary and recreated by an
isolated source installation of Fab7 `0.3.0`. Its canonical
`src/extension.py` imports `src/helper.py`; the generated source test passed,
and two Claude-and-Codex package builds matched artifact SHA-256
`c0b939a098aa204b2142cd6aab138ca5e0be006c6112407d1d4163cf4c67f69b`
and source SHA-256
`0b497476a48b4e998919c68ee8f1de7663d15c73a8d90471f9fd80eb9c01789f`.
The packaged executable contained both modules and omitted tests.

In a disposable home, real Claude Code `2.1.217` and Codex CLI `0.145.0`
installed that local snapshot. Diagnosis passed with both integrations,
`muslin start --json` reported Fab7 `0.3.0`, partial uninstall preserved the
Codex integration and executable, and final uninstall removed the snapshot.

External proof remains intentionally open: ext-registry has not been updated,
hosted CI has not run, no immutable `v0.3.0` artifacts have been published,
and no authenticated model invocation or network registry journey has been
observed. Publication remains unauthorized.
