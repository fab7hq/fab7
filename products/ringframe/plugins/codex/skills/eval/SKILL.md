---
name: eval
description: Judge the work against every open Ask with independent sub-agents; record a verdict with its confidence. Asks nothing.
---

You are running RingFrame Eval inside Codex. Eval judges the work done
so far against every open Ask in this workspace and records a verdict with
confidence. It asks the person nothing, runs none of the project's commands,
and gates nothing: the person decides what to do with the result.

## Eval boundaries and native tools

The coordinator runs exactly one plain `ringframe …` command per CLI call.
Read evidence with a native file-reading tool when available. If Codex exposes
file reads through its command tool, use one plain `cat` command with one quoted
literal file path per call; this also applies to judges and fallback passes.
No `&&`, `;`, pipes, `2>&1`, `head`, `cd`,
`which`, or host version probes. Read completed JSON output directly; never
page or filter it. If the CLI is missing, report `uv tool install ringframe`
and stop. Never write ledger records by hand.

Judges use those file-reading options and read-only Git
commands (`git diff`, `git show`, `git log`), one plain `git …` command per
shell call. Keep project files read-only and write only assigned outputs under
`.fab7/rf/tmp/` in the project workspace, never under the skill directory.
Sub-agents do not write the ledger, do not edit project files, and do not run the
project's build or tests. Apply the same restrictions during fallback passes.

Delegation is part of this skill: use four native sub-agents, one intent judge
followed by three assessors. Give each child its task, the exact output schema,
input paths, and a separate assigned output path. Do not supply your own
verdict or another assessor's findings. While the intent judge works, inspect
the brief and prepare the assessor tasks; while assessors work, prepare the
close command without reading their drafts.

Use the exposed native sub-agent tool, such as `collaboration.spawn_agent`,
with the host's supported completion and follow-up tools. Invoke delegation
tools directly when required by their schema, not inside a shell or code-mode
wrapper. Give each judge a task name unique to this Eval. When the tool exposes
`fork_turns`, set it to `"none"` and put the complete judge instructions in
`message`: each judge needs a fresh context, without the coordinator's history.
Keep the four judges in separate agent contexts.

Collect completed command and agent results before interpreting them. A
pending result, empty initial output, or scheduling delay is not evidence
that delegation is unavailable. Wait for the intent output before launching
assessors, and for all assessor outputs before closing.

In Codex code mode, emit the entire awaited command result with `text(...)`,
including status and session ID. If `functions.exec` yields a cell ID, use
`functions.wait`; if `exec_command` returns a running `session_id`, poll with
`write_stdin` and empty input until it exits. Retain each output. Use the
native agent completion tools for children; a spawn acknowledgement is not
a completed judgement.

Only if the native agent tool is absent or explicitly reports unavailability,
run all four passes yourself sequentially from fresh readings of the files.
Mark every output `"independence":"shared_context"`, record the reason in the
intent judge's `limitation` field and assessors' `basis_notes`, and disclose it
in the report. Do not mix abandoned child drafts into fallback outputs. If
children are still running, stop them before reusing their output paths.
A file/tool permission denial is not grounds to bypass host permissions;
report the failure and stop if the required evidence or output is inaccessible.

## 1. Open

Run `ringframe eval open --json` once; keep `eval_id`, `brief_path`, and
`brief.sha256`. The brief lists the open Asks in order, their `prompt_path`
relative to `.fab7/rf/`, the anchor, subject, changed paths with line counts,
and counts of unrecorded prompts after each Ask.

- Exit 2 `eval.no_open_ask`: report "nothing to evaluate: no open Ask" and stop.
- Exit 3 `eval.anchor_unknown`: report it and stop; the person can supply
  `--anchor <commit>` next time.
- Exit 2 `eval.already_open`: continue with the ID in `detail` and its brief
  at `.fab7/rf/evals/<eval_id>/brief.json`. Reuse the original brief digest
  from that Eval's open result; if it is unavailable, report that limitation
  and stop instead of guessing a digest or reopening.
- Other failures: show the error and stop. Polling a running command does not
  rerun `eval open`.

## 2. Intent: one sub-agent

Give the intent judge `brief_path` and `brief.sha256`. It reads the brief and
each Ask's prompt in order, then writes the effective intent as numbered items,
one obligation each, in the Asks' own words. Unconfirmed Asks are context, not
obligations; never add an obligation no confirmed Ask states.

When a later Ask changes an obligation, mark the earlier item `revised` and
add the new text as a new `active` item, or mark it `withdrawn`. Name the later
Ask in `by_ask_id`. If `previous_evals` is present, read the latest one's
`intent.json` first; preserve IDs and wording of unchanged obligations so the
delta can match them. Add, revise, or withdraw only what later Asks require.

Write `.fab7/rf/tmp/eval-<eval_id>-intent.json` using this shape. Replace
placeholders and example values with the actual evidence; each `status` is
one of `active`, `revised`, or `withdrawn`. Include `by_ask_id` for revisions
and withdrawals. Use the reported model identity when available; do not guess it.

```json
{"schema":"ringframe.eval-intent/1","brief_sha256":"<brief.sha256>",
 "judge":{"host":"codex","model":"<model id>","angle":"intent","independence":"sub_agent"},
 "items":[{"id":"i1","text":"<one obligation>","ask_id":"<source Ask ID>","status":"active","note":"<relevant context>"}]}
```

## 3. Assessors: three independent sub-agents

Launch `coverage`, `drift`, and `adversary` together when host capacity permits;
otherwise schedule separate agents as capacity becomes available. Each receives
`brief_path`, `brief.sha256`, the completed intent file path, and its angle.
Each reads the brief, intent, and anchor-to-subject change within the project:
`git diff --relative <anchor> <subject> -- .` for a commit, or
`git diff --relative <anchor> -- .` for the worktree. Inspect untracked paths
listed in the brief too. For a committed subject, read file content from that
commit with `git show`; use current files only for a worktree subject.

Each writes `.fab7/rf/tmp/eval-<eval_id>-<angle>.json` using this shape:

```json
{"schema":"ringframe.eval-judgement/1","brief_sha256":"<brief.sha256>",
 "judge":{"host":"codex","model":"<model id>","angle":"coverage","independence":"sub_agent"},
 "votes":[{"item":"i1","vote":"yes","reason":"<file evidence for this vote>"}],
 "drift":[{"path":"<changed path>","finding":"<evidence>","classification":"required"}],
 "basis_notes":[],"commands_run":[]}
```

Replace example values with the judge's angle and evidence. Every `active`
item gets exactly one `yes`, `no`, or `unknown` vote. Every judge, whatever its
angle, classifies every changed path as `required`, `consequence`, or
`unexplained`; the CLI refuses missing path classifications. Record actual
Git commands in `commands_run` (empty only if none ran), and ambiguities about
the intent in `basis_notes`.

- `coverage`: is each active item met by the change? Vote `yes` only with
  file evidence; `unknown` when the repository cannot establish it.
- `drift`: lead with the paths: is each change required by an item, a reasonable
  consequence of one, or unexplained by any Ask? Vote the items too.
- `adversary`: look for missing cases, wrong behaviour, and untested claims.
  Vote `no` when you can point at a failure, `yes` when the evidence supports
  the obligation after scrutiny, and `unknown` when you cannot establish it.

## 4. Close

After all four outputs are complete, run
`ringframe eval close --eval <eval_id> --intent @<intent file>
--judgement @<coverage file> --judgement @<drift file> --judgement
@<adversary file> --json`.

On a reported input-validation error, ask the responsible judge to correct
its file without changing unrelated findings; in fallback, correct your own
file. Retry after the correction. If the same error recurs, its cause is
unclear, or it is not input validation, show the error and stop. Do not invent
votes or report an Eval as completed when closing failed.

## 5. Report

Start with the recorded `verdict` and `confidence`; confidence measures judge
agreement, not the probability of correctness. Show the item table (text,
majority, agreement, three votes), omission items, and commission paths with
agreement beside the unrecorded-prompt count that may explain them. Include
`delta` when present, limitations, `eval_id`, and the record path
`.fab7/rf/evals/<eval_id>/record.json`.

Never soften `drifted` or `incomplete`, never present the verdict as certain,
and never ask the person anything. Fixing is native work or a new
`$rf:ask`, followed by `$rf:eval`; `$rf:seal` closes the work
whenever the person decides.
