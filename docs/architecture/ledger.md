---
title: Fab7 Ledger and Gate
type: architecture
status: implemented
owner: architecture
last_updated: 2026-07-19
authority_for:
  - persisted record contract
  - append-only rule
  - freshness rule
  - merge readiness
---

# Fab7 ledger and gate

## Storage

Each work item owns one UTF-8 JSONL file:

```text
.fab7/records/<normalized-work-item>.jsonl
```

Fab7 serializes keys deterministically, requires a final newline, rejects
duplicate JSON keys and record ids, and replaces the file atomically while
holding a bounded per-ledger writer lock. Git enforces history: relative to the
comparison base, a ledger may be added or receive a byte-for-byte append; it
may not be edited, deleted, truncated, or renamed.

## Records

Both record types have exactly these common fields:

| Field | Meaning |
|---|---|
| `v` | record version, currently `1` |
| `id` | generated `rec_<uuid>` identity |
| `type` | `claim` or `evidence` |
| `work_item` | normalized ledger owner |
| `created_at` | UTC observation time |
| `actor` | explicit actor or Git-user-derived fallback |
| `git_ref` | commit associated with the record |
| `summary` | human-readable description |

A claim adds no fields. It means “this work item is complete” and becomes the
gate target when it is the latest claim in the ledger.

Evidence adds:

| Field | Meaning |
|---|---|
| `claim` | claim id in the same ledger |
| `command_digest` | SHA-256 of the argv Fab7 executed without a shell |
| `exit_code` | observed process exit code; timeout is `124` |
| `output_digest` | SHA-256 of captured stdout and stderr |

Callers cannot submit an asserted exit code. `fab7 verify` owns process
execution and observation. The summary retains only the executable name; full
argv and raw output are reduced to digests so the ledger does not become a
secret or transcript store. Raw output is replayed to the caller.

## Freshness and readiness

`fab7 ci-check` passes only when all of the following are true:

1. every ledger is structurally valid;
2. ledger changes relative to the comparison base are append-only;
3. no non-ledger working-tree change is present;
4. the selected work item has a claim;
5. the latest claim has linked evidence with exit code `0`;
6. the evidence commit is an ancestor of the proposed head; and
7. only `.fab7/records/` changed between the evidence commit and the evaluated
   repository state.

Missing, malformed, failed, rewritten, unknown, dirty, and stale states fail
closed. There are no waivers or policy switches in the current product.
