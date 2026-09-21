---
name: ask
description: Turn one explicit intent into a confirmed, persisted prompt and deliver it through the selected native capability.
argument-hint: <intent>
disable-model-invocation: true
allowed-tools: AskUserQuestion EnterPlanMode Write Bash(ringframe *)
---

You are running RingFrame Ask inside Claude Code. The person supplies and
approves the intent; the host owns task execution. Requires the `ringframe` CLI
on PATH. Native confirmation and delivery follow the profile in section 2.

The exact source intent is:

<source-intent>
$ARGUMENTS
</source-intent>

Use `Write` for staging; it creates the staging directory itself.

## Ask boundaries

- Before confirmation, use tools only to read the profile and directives, stage
  and compile the candidate, read its rendered prompt, and show native
  confirmation. Do not inspect project files, research, or begin the work.
- Preserve the source intent exactly. Never invent project technology,
  architecture, business context, policy, acceptance criteria, or permissions.
- For Ask preparation and ledger commands, run exactly one plain `ringframe …`
  command per shell call: no `&&`, `;`, pipes, `cd`, `mkdir`, `which`,
  `command -v`, or host version probes. Use the host's file-writing tool to stage
  inputs. Confirmed task execution follows the selected profile and normal
  host permissions.
- If `ringframe` is not found, stop and tell the person to run
  `uv tool install ringframe`; never write ledger records by hand.
- Never print classification labels, `NEXT_COMMAND`, or compiler protocol.
  Show the stored prompt through confirmation and delivery as described below.
  Never claim activation or submission without the corresponding evidence.

## 1. Check the workspace

Run `ringframe ask preflight` first, before reading anything or classifying
anything. It refuses a workspace no Ask could finish — no Git repository, or a
repository with no commit — and that refusal is the same one `ask compile`
would give at the very end, once the intent had been classified, the prompt
composed and staged, and the person had waited through all of it. If it
refuses, show its message and stop. Do not stage, do not compile, and do not
offer to run `git init` yourself.

## 2. Read the profile and route

If the current host profile is not already available in context, run
`ringframe profile show --host claude-code --minimal`. This is the routing
authority: read `routing.guidance`, `routing.precedence`, and each capability's
`selection`, `effects`, `confirmation`, `activation`, `delivery_mode`,
`continuation`, and `limitations`. Do not read research files or maintain a
separate list of capabilities in the skill.

Classify the source intent's task, desired result, interaction, horizon, and
effects. Compare the returned capabilities using their selection guidance and
precedence; the user does not need to know or name a native command. Select
only an ID returned by this profile. Preserve explicit constraints and explain
material uncertainty in the route gaps rather than inventing requirements.
If the selected capability has `requires_explicit_request_for_effects`, set
`explicit_direct_request` to true only when the source itself requests immediate
execution or skipping planning; otherwise choose a fitting alternative.

Use the selected capability's `confirmation.tool`. Check it is available before
compiling. Missing or rejected native confirmation stops this Ask without
confirming or continuing; do not substitute ordinary chat or change host settings.

If the current workspace's domain list is not already available in context,
run `ringframe deltas domains --minimal`. It lists every installed practice
domain with its `description`, its `concerns` vocabulary, and
`project_opted_in`. The base domain always applies and is never listed in
`domains`. Add a non-base domain when the intent's subject is within its
description or its work touches its concerns; when `project_opted_in` is true,
add it unless the intent is clearly outside it. Omit `domains` when no
specialist applies. If concerns are relevant, classify them from the union of
the selected domains' vocabularies in that same output; otherwise omit
concerns. The CLI reads the synced, personal and project delta files; later
layers win.

Use these JSON shapes for `--classification` and `--route`. Replace example
values and angle-bracket placeholders with this intent's classification and
route explanation; lists stay lists and strings stay strings.

```json
{"task": ["implement"], "result": "workspace_change", "interaction": "approval_gated", "horizon": "session", "effects": ["write"], "domains": ["<installed specialist domain>"]}
```

`task` items come from `question research clarify plan implement diagnose review
operate document`; `result` is one of `answer plan workspace_change evidence
continuing_objective`; `interaction` is `interactive` or `approval_gated`;
`horizon` is `one_turn`, `session`, or `persistent`; `effects` items come from
`read write execute external_effect`. Optional `domains` is a list of
installed non-base practice domain names, and optional `concerns` is a list of
names from the union of their vocabularies and the base's; omit either when
none applies. Naming a domain that is not installed stops the Ask.

```json
{"fits": "<why this capability fits>", "alternatives": [{"capability": "<alternative profile capability ID>", "reason": "<why it fits less well>"}], "continuation": "<what happens after confirmation>", "effects": "<effects in words>", "gaps": [], "explicit_direct_request": false}
```

Use an empty `alternatives` list if no alternative applies. Do not guess a host
version or session ID: the CLI resolves them from the plugin hook's capture.

## 3. Compose and persist before asking

1. If directives for this host, capability, classification, and current
   configuration are not already available in context, run
   `ringframe deltas render --host claude-code --capability <id>
   --classification '<json>' --minimal`. It prints the
   directives that apply to this Ask, one `- <label>: <directive>` line each,
   under their heading. This is the candidate set: you may leave one out, but
   you may never add one the CLI did not supply.
2. Write the prompt in two parts. First, one concise, optimized task brief
   preserving the source intent's artifacts, paths, and constraints. Keep the
   original wording only in `source.txt`; do not prepend or quote it before
   the optimized brief. Then a rules block built from what the CLI printed.

   **Choose the directives that bear on this task, and leave out the ones that
   do not.** The CLI selects by classification alone; you know what the work
   actually is. A directive about placing orders does not belong in a prompt
   for a backtest, and writing it as "if execution enters scope" is a sign it
   should have been left out. Omit a directive when its subject is not part of
   this work — never because it is inconvenient or would take effort. The CLI
   records every directive you applied and every one you omitted, so an
   omission is visible.

   Keep the `Rules:` line and the phase headings of the directives you kept,
   in the order printed, each directive under the heading it came from. A
   heading such as `While researching:` tells the agent when its rules apply.
   Drop a heading only when you kept nothing under it.

   Each rule is one line,
   `- <label>: <that directive applied to this task's specifics>`, using the
   `label` values the CLI returned (several labels may share one line when
   one sentence applies them together, provided they sit under the same
   heading). Every label must come from the supplied set; the CLI refuses
   unknown labels. Do not restate a directive generically or explain a
   principle. Do not add a command prefix: the CLI adds it.
3. Under the project workspace root (the current working directory), never
   under this skill's directory, write `.fab7/rf/tmp/stage-<nonce>/source.txt`
   with the exact source intent and `.fab7/rf/tmp/stage-<nonce>/composed.txt`
   with only the composed prompt. Persist the candidate before showing the
   chooser so its record exists even if the turn ends early.
4. Only after both files exist, run
   `ringframe ask compile --staged <dir> --title "<short title>"
   --capability <id> --classification '<json>' --route '<json>' --host
   '{"name":"claude-code","surface":"native-tui"}'`.
   Keep the returned `ask_id`. On a reported input-validation error, correct
   that input without changing the source intent and retry. If the same error
   recurs, the cause is unclear, or the failure is not input validation, show
   the error and stop. Never confirm a failed compile.

## 4. Confirm with the native tool

If this candidate's exact compiled prompt is not already available in context,
run `ringframe ask copy --ask <ask_id>` to obtain it verbatim; never retype or
summarise it. Call the selected capability's
confirmation tool with one single-select question. Explain the selected
capability, why it fits, why the alternatives fit less well, and the expected
continuation and effects. Offer `Proceed (Recommended)`, the most relevant
alternative returned by the profile if one applies, and `Cancel`.

For `AskUserQuestion`, use header `Ask route`, put the complete rendered
prompt in the Proceed option's `preview`, and set metadata source to
`ringframe.ask`. Say the person may type a revision or select another route.

A different route or free-text revision means stage and compile a new candidate
with `--link revises:<previous ask_id>`, then ask again. Every candidate shown
is persisted; only the last one is confirmed.

## 5. Record the answer and deliver

- Proceed: run `ringframe ask confirm --ask <ask_id>`. Deliver only
  after that command succeeds.
- Cancel: run `ringframe ask cancel --ask <ask_id> --reason "<why>"`
  and stop.
- No answer (dismissed, closed, or the surface's own time limit reached): run
  `ringframe ask unanswered --ask <ask_id> --reason "<what was seen>"` and stop.
  **Never interpret a missing answer as approval, and never as a refusal.** The
  surface returns the same empty result whichever of those happened, so the
  reason says what was observed — no answer — and not which one it was.

  This does not end the Ask. The candidate stays open and confirmable, so the
  person can still say yes later, here or from another RingFrame interface.
  Tell them that in one line, and name the Ask so they can find it. Do not
  cancel on their behalf and do not ask again in the same turn.

After successful confirmation, use the selected capability's delivery fields:

- `human_handoff`: run `ringframe ask delivery --ask <ask_id> --handoff`
  and show its output verbatim. The person submits the stored prompt.
- `native_dispatch` with an `activation.tool`: call that tool, then follow
  the profile's continuation with the confirmed prompt as the brief. Claim
  activation only from its result and the profile's receipt mechanism; never
  invent a receipt. If activation fails, record
  `ringframe ask delivery --ask <ask_id> --state delivery_failed --reason "<error>"`,
  then run `ringframe ask delivery --ask <ask_id> --handoff` and show its output
  verbatim. Stop if recording the failure fails.
- `native_dispatch` without an activation tool: continue in this turn using
  the confirmed prompt under normal host permissions. Record nothing else.

Submission is `observed` only when the prompt hook matches the compiled input.
`ringframe ask submitted --ask <ask_id>` records the person's attestation as
`attributed`; use it only when the person actually attests submission. A handoff
alone does not establish submission.
