# How a prompt gets built

You type an intent. What reaches your agent is that intent, rewritten as a
clear brief, with your standing rules listed underneath.

```
Add slippage and commission modelling to the backtester.

Rules:
- KISS: This project is a backtester; prefer one obvious function over a class.
- Cost Realism: Account for every cost exactly once — commission, spread, …
```

Two parts, and they come from different places. **The brief is written by your
agent**, from your words. **The rules are chosen by the CLI**, from YAML files.
Your agent never picks which rules apply, and the CLI never writes prose.

Your original wording is kept untouched in `source.txt`. It is not pasted in
front of the brief.

## Picking the route, then the rules

Before anything is written, the Ask skill asks two questions.

**Where should this go?** It reads
`ringframe profile show --host <host> --json` — the list of things your agent
can do, and when each one fits. It decides from that. You never have to name a
native command yourself.

**Which rules apply?** It describes your task to the CLI — is this planning or
implementing, does it write files, what is it about — and runs
`ringframe deltas render`, which prints the rules that match. The skill weaves
those into the brief.

Then it calls `ringframe ask compile`, shows you the finished prompt, and waits.
Nothing is delivered until you confirm.

The CLI checks that the route your agent named really exists in the profile and
records which profile it used. Whether the route was a *sensible* choice is a
judgement call by a model, and RingFrame reports it rather than guaranteeing it.

## Three ways to stage a prompt

Every Ask stages `source.txt` plus exactly one of these:

| File | What the CLI does with it | Recorded as |
| --- | --- | --- |
| `composed.txt` | Your agent already wrote the `Rules:` lines. The CLI checks every label is one it supplied. | `composed` |
| `body.txt` | Your agent wrote only the brief. The CLI appends the rules itself, word for word. | `body` |
| `prompt.txt` | The whole prompt, as-is. Nothing is added. | `prompt` |

`composed.txt` is what the shipped skills use, because applying a rule to your
actual task reads better than pasting it. `body.txt` is the plain baseline.
`prompt.txt` is the old form, kept working.

The labels on each `Rules:` line are traceability tags. The CLI verifies each
label names a rule it actually supplied, and records which rules were applied
and which were dropped. It does **not** judge whether the sentence applies the
rule correctly — that is prose, and no check can settle it.

## Where the rules come from

Three layers, merged by rule id, later winning:

1. `~/.fab7/rf/config/` — what you synced from the marketplace
2. `~/.fab7/rf/overrides/` — your personal changes
3. `<project>/.fab7/rf/deltas/` — this project's changes

[Rules](delta.md) covers the file formats, how merging works, priorities,
budgets, and worked examples.

## Looking at what happened

```sh
ringframe deltas domains --json
ringframe deltas list --effective --json
ringframe deltas render --host codex --capability native_plan \
  --classification '{"task":["implement"],"result":"workspace_change","interaction":"approval_gated","horizon":"session","effects":["write"],"concerns":["api_surface"]}'
```

## CLI output

Fetch commands separate conversation context from complete observation:

| Commands | `--minimal` | `--json` |
| --- | --- | --- |
| `profile show` | Routing guidance and actionable capabilities | Full profile and provenance |
| `deltas domains`, `deltas list` | Domain vocabulary or directive content | Full catalogs and selection metadata |
| `deltas render` | Applicable directive text and phase headings | Text, entries and selection provenance |
| `ask list`, `ask show`, `ask resolve` | Identity, state and selection/next-action data | Full Ask summaries |
| `eval list` | State, verdict, confidence and Ask basis | Full Eval summaries |
| `seal check`, `ledger verify` | Verification result and failure findings | Complete verification result |

The flags are mutually exclusive and may appear before or after the subcommand.
Without either flag, fetch commands retain their normal output: pretty JSON for
structured results and plain text for `deltas render`. Minimal profile output
omits empty activation/receipt objects; absence means no declared mechanism.

Actions have one concise default response and reject both output flags:
`init`, `sync`, `ask compile/copy/confirm/cancel/submitted/delivery`,
`eval open/close`, `seal create`, `sessions capture/prune`, and `export`.
Structured responses are compact JSON; `ask copy` returns the exact prompt,
and delivery handoff returns the handoff instructions as plain text.
Errors retain their code and actionable details.

This replaces the earlier action output flags. Remove `--json` and `--minimal`
from action invocations, including hook scripts. Observe full persisted detail
through fetch commands or the corresponding ledger and artifact files; do not
repeat an action to inspect its result.

Concise does not mean dropping required inputs: `eval open` retains the brief
digest needed by judges, `eval close` retains report findings, and `seal create`
returns the receipt path and decision facts. Output selection does not change
stored records.

The Ask skill reuses applicable profile, domain, directive and exact compiled
prompt results already in context. Each reuse condition sits beside its command;
new candidates and confirmation events still use their own action calls.

Every Ask records the same detail under `ask.compiled.data.compiler`, so you can
always reconstruct which rules were in force for a prompt written months ago.

One caveat, stated plainly: a prompt that compiled cleanly is not evidence it is
a better prompt. That question belongs to [Eval](../commands/eval.md), which
compares the resulting diff with what you asked for.
