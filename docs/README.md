---
title: Fab7 Documentation
type: index
status: implemented
owner: project
last_updated: 2026-07-22
---

# Fab7 documentation

The active documentation separates the proof core, owner-accepted onboarding,
released extension distribution, its marketplace-migration maintenance, and
deferred Denim.

## Product

| Document | Owns |
|---|---|
| [`product/vision.md`](product/vision.md) | product identity, promise, and boundaries |
| [`product/roadmap.md`](product/roadmap.md) | completed baseline, onboarding, extension distribution, active maintenance, and deferred Denim |

## Architecture

| Document | Owns |
|---|---|
| [`architecture/overview.md`](architecture/overview.md) | executable boundary and data flow |
| [`architecture/ledger.md`](architecture/ledger.md) | record format, append rules, freshness, and gate |
| [`architecture/distribution.md`](architecture/distribution.md) | bootstrap, layouts, host plugins, catalog, package, and extension lifecycle contracts |

## Plans

| Document | Owns |
|---|---|
| [`plans/onboarding.md`](plans/onboarding.md) | Fab7-only onboarding work packages, dependency order, verification, and closure gate |
| [`plans/ext-registry.md`](plans/ext-registry.md) | extension implementation evidence, publication order, network acceptance, and stop rules |
| [`plans/marketplace-migration.md`](plans/marketplace-migration.md) | managed marketplace migration contract, proof, and maintenance release gate |

[`status.yaml`](status.yaml) points to this exact authority set. Repository
engineering guidance lives in root [`AGENTS.md`](../AGENTS.md).

New-user operating steps live in root [`RUNBOOK.md`](../RUNBOOK.md). The
runbook follows the authorities above; it does not redefine product,
architecture, plan, or status facts.

Product documents own outcomes. Architecture documents own system shape and
contracts. Plans own finite implementation sequence and gates. Do not repeat
those facts across categories.
