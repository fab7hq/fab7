---
name: seal
description: Close the open Asks with one disposition; record the latest Eval as a fact and the receipt.
argument-hint: <accepted|rejected|deferred|abandoned> [note]
disable-model-invocation: true
allowed-tools: AskUserQuestion Bash(ringframe *)
---

You are running RingFrame Seal inside Claude Code. A Seal is the person's
decision to close the open Asks; it merges, publishes, deploys, or certifies
nothing, and no Eval verdict blocks it.

Arguments: `$ARGUMENTS`.

## Seal boundaries and native confirmation

Requires the `ringframe` CLI and the native `AskUserQuestion` tool in this turn.
If either is unavailable, explain the missing requirement and stop; for a
missing CLI, report `uv tool install ringframe`. Do not change host settings
or substitute ordinary chat for native confirmation. If the host rejects the
confirmation call, the chooser is cancelled or dismissed, or no answer is
returned, do not create a Seal.

Use the shell for `ringframe` only, exactly one plain `ringframe …` command
per call. No `&&`, `;`, pipes, `2>&1`, `head`, `cd`, `which`, or host version
probes. Read the completed JSON output directly; never page or filter it.
Collect a running command's final result before proceeding; never rerun a
pending `seal create` or claim success from empty output.

## 1. Read the open work

Run `ringframe eval list --json` and `ringframe ask list --json` in separate
calls. Identify the open Asks and the latest completed Eval sharing an open
Ask, including its verdict and confidence. If there are no open Asks, report
nothing to close and stop. If either command fails, show the error and stop.

Seal binds the latest matching Eval by default; pass `--eval <eval_id>` only
when the person names another. An Eval's absence, age, changed subject, or
verdict does not require a new Eval or block the person's decision.

## 2. Confirm the decision

Show the open Ask titles, the selected Eval's verdict and confidence (or
"no Eval"), the disposition, and any supplied note through native confirmation.
Dispositions are `accepted`, `rejected`, `deferred`, and `abandoned`; each closes
the Asks. Never choose a disposition for the person if none was supplied.

Use `AskUserQuestion` with one single-select question and header `Seal`.

Offer confirmation of the supplied disposition, a way to select another, and
Cancel. If no disposition was supplied, ask the person to select one. Respect
the tool's option limit; name all valid dispositions in the question text and
allow a typed choice when they cannot all fit in the options.

Preserve notes verbatim as `--note "<text>"`. A note alone or an ambiguous answer
is not confirmation: show the updated decision and ask again. Proceed only on
an explicit disposition choice or confirmation of the displayed decision.
Do not ask for an acknowledgement or a justification; the decision is theirs.

## 3. Create

Run `ringframe seal create --disposition <d> [--eval <eval_id>]
[--note "<text>"] --json` only after confirmation. The actor is the interactive
person; do not pass `--actor` or `--authority` unless the person explicitly
names a pre-authorized policy. Do not infer policy authority from the verdict.

## 4. Report

On success, show the receipt path, sealed Asks, recorded Eval fact (`verdict`,
`confidence`, `subject_matches`, or no Eval), and limitations verbatim.
On refusal, show `refusal_codes` verbatim and stop:

- `seal.no_open_ask`: nothing to close.
- `seal.eval_missing`: the named Eval does not exist or is not completed.
- `seal.eval_unrelated`: the named Eval shares no open Ask.
- `seal.authority_missing`: no matching authorization for the declared actor.

For any other failure, show the error and stop without claiming a receipt.
Downstream consumers check a receipt with
`ringframe seal check --seal <seal_id> --json`.
