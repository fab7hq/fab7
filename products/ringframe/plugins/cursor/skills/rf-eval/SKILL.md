---
name: rf-eval
description: Judge the work against every open Ask with small, checked judging tasks RingFrame hands out; record a verdict with its confidence. Asks nothing.
disable-model-invocation: true
---

You are running RingFrame Eval inside Cursor. RingFrame reads the change, hands
out small judging tasks, checks every citation a judge gives against its
source, and writes the report. You only dispatch: you spawn the tasks
RingFrame gives you and wait for them. You read no patch, brief, window,
document, task file or judgement, and you judge nothing yourself. Eval asks
the person nothing, runs none of the project's commands, and gates nothing.

## Invocation

The invocation's arguments are the text after `/rf-eval` in the person's
message.

```text
/rf-eval [--override '<json>'] [gather | debate <eval_id>] [role=model/effort ...]
```

- **`--override '<json>'`:** RingFrame configuration, typed by a tool that
  runs RingFrame or the person. Add it, unchanged, to `ringframe eval open`.
  Never write one yourself or edit it.
- **`gather`:** open the Eval and stop. RingFrame gathers the change as the
  Eval opens, once, for every task that follows in any harness; report the
  Eval ID and that its debate runs anywhere with `/rf-eval debate <eval_id>`.
- **`debate <eval_id>`**, or **`continue <eval_id>`:** do not open; run that
  Eval's tasks here, from what was gathered.
- **Roles** are `map`, `reduce` and `confirm`. In `confirm=<model>/high` the
  model comes before `/` and the effort after; either side may be empty
  (`map=/low`). The earlier names still work: `trace=` and `drift=` mean
  `map=`, `coverage=` means `reduce=`, `adversary=` means `confirm=`;
  `intent=` and `context=` name roles that no longer run: say so once and
  ignore them, as any other role word. Other words are the person's and
  change nothing here.

Before opening, read `config.toml` in this skill's directory, beside this `SKILL.md`, once: its `[eval] parallel` is how many tasks
may run at once (4 when the file is missing or unreadable; say so once in the
report). Each role's model and effort are in this plugin's agent definitions,
`rf-map`, `rf-reduce` and `rf-confirm`, in the `agents` folder two folders above this skill's directory, as an absolute path: RingFrame reads them
when you pass that folder as `--agents-from <folder>`; do not read them
yourself. The invocation's role words win over them, key by key: pass those
as `--agents '<json>'`, with only the keys the words set. Never guess a model
or an effort.

## Commands

Run exactly one plain `ringframe …` command per call. No `&&`, `;`, pipes,
`2>&1`, `head`, `cd`, `which`, or host version probes. Read completed JSON
output directly. If the CLI is missing, report that the Fab7 installer is
needed and stop. Never write ledger records, task files or task outputs, and
never run `ringframe eval submit`: the judges do.

A repository where `ringframe init` was never run has no RingFrame
workspace, and every `ringframe` command here says so: show that message and
stop. Setting the repository up is the person's to do, at its root.

## 1. Open

Skip this for `debate` or `continue`, but resolve the roles the same way; for
`gather`, stop after it. Run `ringframe eval open --host cursor --agents-from <folder>` once, with the
invocation's `--override` when it has one, adding `--agents '<json>'` with the
invocation's role words only, for example `--agents '{"confirm":{"model":"<model>","effort":"high"}}'`; no
`--agents` flag when it has none. Keep `eval_id`.

- Exit 2 `eval.no_open_ask`: report "nothing to evaluate: no open Ask" and
  stop.
- Exit 3 `eval.anchor_unknown`: report it and stop; the person can supply
  `--anchor <commit>` next time.
- Exit 2 `eval.already_open`: continue with the Eval ID in `detail`.
- Other failures: show the error and stop.

## 2. Dispatch until done

Repeat:

1. Run `ringframe eval next --eval <eval_id> --parallel <parallel> --host cursor`, adding
   the same `--agents-from <folder>` and `--agents '<json>'` as §1: for an
   Eval opened elsewhere, it is how this harness's tiers reach its tasks.
   Add `--returned <task id>` once for every sub-agent that has finished since
   the last `next`, whatever it replied, and for every one that could not
   start: RingFrame hands a task that came back without an accepted output
   out again at once.
2. When its `state` is `done`, go to §3.
3. Spawn one sub-agent for every entry of `tasks`, all of them together: one
   `Task` call per task, all in one message: `subagent_type` the task's
   `agent`, one of this plugin's `rf-map`, `rf-reduce` and `rf-confirm`
   (listed among your subagents); `prompt` the task's `prompt`, verbatim and
   nothing else; a `description` naming the task id. Pass no model: the
   judge runs on the session's model, and the task's `effort` is already in
   its task file. This skill is the explicit request to spawn sub-agents.
4. Wait until every sub-agent you spawned has replied. A reply is one line,
   `<task id> accepted` or `<task id> failed: <reason>`; read nothing else and
   check nothing. The `Task` result is the reply.
5. Go back to 1, naming with `--returned` every sub-agent that has replied
   since the last `next`, each once. When `tasks` is empty and the state is
   `running`, other tasks are still out: wait for your sub-agents, then run
   `next` again.

A spawn refused because too many agents or threads are open (such as "agent
thread limit reached") is not the tool being unavailable: keep that task,
wait until one of your running sub-agents has replied, and spawn it then.
Only a sub-agent tool that is absent or disabled stops the Eval.

A spawn acknowledgement is not a reply. A sub-agent that could not start, or
ended without its line, has still finished: name its task with `--returned`
in the next `next`, as for any other. Never wait for a task's time to run
out. If the sub-agent tool is absent or reports it is unavailable,
report that this harness cannot run the Eval's judges now, give the command
`/rf-eval debate <eval_id>` for another harness, and stop. Never do a task
yourself.

## 3. Report

Run `ringframe eval show --eval <eval_id> --summary` once and show its output
to the person exactly as printed: the report's head, what each section holds,
and where the whole report is, which RingFrame writes from the record. Do not
print the whole report. Add nothing to it, reorder nothing, and compose no table, summary or
list of your own; do not read `record.json` to build one. If the command
fails, show its error and the path `.fab7/rf/evals/<eval_id>/eval.md`.

Never soften `drifted` or `incomplete`, never present the verdict as certain,
and never ask the person anything. Fixing is native work or a new `/rf-ask`,
followed by `/rf-eval`; `/rf-seal` closes the work whenever the person
decides.
