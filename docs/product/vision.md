---
title: Fab7 Product Vision
type: product
status: accepted
owner: product
last_updated: 2026-07-22
authority_for:
  - Fab7 positioning
  - Fab7 product boundaries
  - relationship between proof core and distribution layer
---

# Fab7 product vision

Fab7 is a small, host-neutral proof gate for work performed by agents and
humans. It turns a completion claim and an executed verification command into a
durable repository record, then rejects the claim when that proof is absent,
failed, rewritten, or stale.

## Product thesis

Agent completion language is not proof. A repository needs a deterministic
answer to four questions:

1. What is the latest completion claim for this work item?
2. Which command did Fab7 actually execute for it?
3. Did that command pass against this Git state?
4. Did implementation files change afterward?

Fab7 answers only those questions. Git remains the durable source of code and
history; humans retain authority over merge, release, deployment, spend, and
residual risk.

## Product promise

```text
An agent or human makes a completion claim.
Fab7 executes the chosen verification command and records the observation.
Fab7 blocks readiness when the latest claim lacks fresh passing evidence.
```

## Product boundary

Fab7 core models only completion claims and executed evidence. It does not
model plans, scopes, waivers, approvals, decisions, arbitrary events, or
workflow-specific records. Those concepts may live in normal repository files
or external extensions until a measured product need justifies another core
contract.

Fab7 is not a planning framework, agent orchestrator, methodology, dashboard,
policy language, extension runtime, or autonomous release operator. Its proof
core remains host-neutral and provider-neutral.

The accepted distribution layer is a thin path around that core:

- a repository-owned script installs Fab7 beneath `~/.fab7/`;
- `fab7 install claude|codex` registers a bundled Fab7 plugin through the
  selected host's native plugin commands;
- the Fab7 init skill creates a second, version-pinned installation beneath the
  current repository's `.fab7/` directory and later project work selects that
  local binary;
- Fab7 installs external registry releases or explicitly approved local source
  through one verified immutable package path and native host plugins.

The separate [`fab7hq/ext-registry`](https://github.com/fab7hq/ext-registry)
owns `catalog.yaml`; [`fab7hq/muslin`](https://github.com/fab7hq/muslin) is the
minimal distribution fixture; and [`fab7hq/denim`](https://github.com/fab7hq/denim)
remains the first product extension. Local source paths never enter the shared
catalog or become mutable runtime links. Extensions communicate with Fab7
through its public binary and structured output, not imports or shared state.

Neither layer expands proof authority, loads extensions into core, or makes
host output accepted evidence. Onboarding is owner-accepted; extension
implementation is complete locally and awaits publication plus network proof;
Denim remains deferred. See
[`../architecture/distribution.md`](../architecture/distribution.md) for the
contracts and [`roadmap.md`](roadmap.md) for the release gate.

See [`../architecture/overview.md`](../architecture/overview.md) for the
implemented executable boundary.
