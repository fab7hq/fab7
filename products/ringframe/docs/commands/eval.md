# Eval

**You asked for some things. Eval looks at what actually changed and asks
several independent judges whether you got them.**

`/rf:eval` in Claude Code, `$rf:eval` in Codex. On Codex, ask for sub-agents
explicitly — see [asking for judges](#asking-for-judges).

```mermaid
flowchart LR
    O[The facts: open Asks, the diff] --> I[What was actually promised?]
    I --> C[Did we get it?]
    I --> D[What changed that nobody asked for?]
    I --> A[What is being glossed over?]
    C --> V[Check and tally]
    D --> V
    A --> V
    V --> R[Verdict and agreement]
```

Eval compares **the diff against what you confirmed**. It finds things you asked
for that are missing, and things that changed that no Ask explains.

It does not watch *how* the work was done. Whether your agent wrote the test
first is not something Eval can see.

The skill tells your agent to ask you nothing and to run no builds or tests
during an Eval. That is an instruction, not a sandbox.

## What it judges against

An Ask is **open** from the moment it compiles until you cancel it or a Seal
closes it. Eval takes every open Ask, in order.

Unconfirmed prompts count as context, not obligations. Confirmed ones are the
obligations — including later revisions that changed them and withdrawals that
dropped them.

Your ordinary chat is never stored. But hooks do count how many plain prompts
went by, which is often what explains a change no Ask asked for.

**Eval needs Git.** It has to diff something against something.

The starting point is, in order: `--anchor` if you gave one, the last Seal's
commit, then the earliest base commit among the open Asks. If none of those
exist it stops and asks. The end point is `HEAD` when your tree is clean,
otherwise the working tree as it stands:

| Subject | What is recorded |
| --- | --- |
| `git_commit` | The commit, and the tree hash — for a nested project, just that project's subtree |
| `worktree` | The path, and a digest over every file's path, mode, and contents, untracked files included |

## The judges

`eval open` writes a brief: which Asks are open, the start and end points, how
many files changed, any earlier Eval covering the same Asks, and the known
limitations. If an Eval is already open over those same Asks, you continue with
that one rather than starting a second.

Then four judges, and they have different jobs:

1. **Intent** — reads the Asks and writes down what was actually promised, marking
   each item `active`, `revised`, or `withdrawn`, traced back to its Ask.
2. **Coverage** — did we get each active item?
3. **Drift** — what changed that nobody asked for?
4. **Adversary** — what is being glossed over?

The last three each vote `yes`, `no`, or `unknown` per item, and label every
changed file `required`, `consequence`, or `unexplained`.

They are meant to run as separate agents that cannot see each other's answers.
If your host genuinely has no sub-agent tool, the skills allow four passes in
one context instead — but that gets marked `shared_context` and the reason has
to be stated. A slow tool or a permission prompt is not a reason to fall back.

`eval close` needs at least three judgement files tied to that exact brief,
votes on every active item, and a label on every changed file. The CLI records
what the judges said about their own identity and independence. It cannot
*verify* they were independent.

## Reading the verdict

| Verdict | When |
| --- | --- |
| `aligned` | Every active item got a yes, and no file is unexplained. |
| `drifted` | An item got a no, or a file came back unexplained. |
| `incomplete` | No active items, votes left unresolved, or the code changed while Eval was running. |

**Confidence is agreement, not correctness.** It is the lowest agreement among
the questions that were actually in doubt. Three judges who all agree and are
all wrong produce high confidence. Read it as "how much did they disagree",
nothing more.

Ties go the cautious way: an item ties to `unknown`, a file ties to
`unexplained`. If nothing was in doubt, confidence is `0.0`. No active items
always gives `incomplete`, and so does code changing underneath the Eval.

## Asking for judges

Your host agent runs the Eval skill and spawns the judges. **The RingFrame CLI
never spawns anything.**

| Host | How the skill asks |
| --- | --- |
| [Claude Code](https://github.com/fab7hq/fab7/blob/main/products/ringframe/plugins/claude/skills/eval/SKILL.md) | Foreground `Agent` calls; `Read` for evidence, `Write` for the judge files |
| [Codex](https://github.com/fab7hq/fab7/blob/main/products/ringframe/plugins/codex/skills/eval/SKILL.md) | Fresh native agent contexts (`fork_turns: "none"` where available) |

On Codex, say so when you invoke it — every time, even with sub-agent tools
already on:

```text
$rf:eval use native sub-agents
```

Those words cannot create a tool that is not there, or force your host to spawn
anything. Your host owns that.

## What is recorded

`evals/<eval_id>/` holds the brief, the intent, each judgement, and the final
record — votes, what was missing, what was unexplained, the limitations, and
what changed since the last Eval of the same Asks.

That comparison matches items by ID first, then by wording, then by overlap.
It is a best effort at "is this the same obligation, reworded", not a proof.

```sh
ringframe eval open
ringframe eval close --eval <eval_id> --intent @intent.json \
  --judgement @coverage.json --judgement @drift.json --judgement @adversary.json
ringframe eval list --json
```

**Eval never blocks [Seal](seal.md).** A bad verdict is information for your
decision, not a gate on it.
