# Rules

**The profile says what your agent can do. The rules say what to tell it while
it does that.**

Rules are standing instructions. You write them once; Ask picks the ones that
fit each task and your agent applies them to the specifics.

There are two kinds, and they answer different questions:

| | **Practice rules** | **Host rules** |
| --- | --- | --- |
| Answer | "However you do this, remember X." | "While in Plan mode, remember X." |
| Chosen by | what the task *is*, and optionally the route it took | which route the Ask took |
| Live in | `deltas/practices/<domain>.toml` | `deltas/<host>.toml` |
| Example | *Write the failing test first.* | *Verify the paths you name exist.* |

Neither kind can give your agent a new ability. That is the profile's job, in
`harnesses/<host>.toml`, and you do not normally edit it.

## Where rules come from

Nothing ships inside the CLI. `ringframe init --global` downloads rules from the
[Fab7 marketplace](https://github.com/fab7hq/fab7); `ringframe sync` is the same
command and is how you update later. `ringframe sync --check` only says whether
a newer release is out, and writes nothing.

Neither runs on its own, so your prompts never change underneath you.

```
~/.fab7/rf/config/       downloaded — sync overwrites this, so do not edit it
  harnesses/<host>.toml    what each agent can do
  deltas/<host>.toml       rules for one route
  deltas/practices/<domain>.toml   rules for a kind of work
  .revision                which release this came from
```

Every configuration file is TOML. **Your changes come from Weft**, in
`~/.fab7/weft/config.toml`: the `[ringframe]` table for everywhere you work,
and `[projects."<path>".ringframe]` for one project. Weft types both into every
`/rf:` command it sends as `--override '<json>'`, and RingFrame applies them
over the downloaded rules.

**Three layers, and the later one wins:** downloaded, then yours, then this
project's.

Under `[ringframe]`, a `deltas` table is keyed by the file's path under
`deltas/`, without `.toml`, and holds that file's keys:

```toml
[ringframe.deltas."practices/software-development"]
render = { core_cap = 6 }

[projects."/Users/me/work/thing".ringframe.deltas."practices/software-development"]
entries = [{ id = "practice.yagni", enabled = false }]
```

Never edit `config/` — the next sync will throw your change away. RingFrame
reads no override folder; one left from an earlier release is reported and not
read, and its content belongs in Weft's `config.toml`.

You only write the fields you are changing. Everything else is inherited.

Without Weft, type the same value yourself: `--override` takes a list of named
layers, applied in order, on `profile show`, `deltas domains`, `deltas render`,
`ask compile` and `eval open`, and each `/rf:` skill passes a leading one on:

```sh
ringframe deltas domains --json --override '[{"layer":"mine","ringframe":{"deltas":{"practices/software-development":{"entries":[{"id":"practice.yagni","enabled":false}]}}}}]'
```

A layer's name is where the CLI says a rule came from. A value it cannot read
stops the command and says what is wrong.

`ringframe init --global --from <dir>` installs from a folder instead of
downloading, for machines with no network. Every prompt records which release
its rules came from, so a receipt tells you what was in force at the time.

## How layers merge

Rules are matched up by their `id`. A later layer changes only the fields it
mentions:

| What your file has | What happens |
| --- | --- |
| nothing | You get everything from the layer below. |
| a rule with an `id` that already exists | Your fields replace those fields. The rest is inherited. |
| a rule with a new `id` | It is added, after the inherited ones. |
| `enabled = false` on a rule | The rule stays configured but stops appearing in prompts. |
| `entries = []` | Every rule in this file is cleared. |
| any other list or single value | It replaces the one below outright. |

Keep ids unique and do not rename them — a receipt written last month refers to
them. Removing your table again restores what you inherited. To clear a list
use `[]`.

For example, reword KISS and switch YAGNI off, for one project:

```toml
[projects."/Users/me/work/thing".ringframe.deltas."practices/software-development"]
entries = [
  { id = "practice.kiss", text = "Keep changes small and direct." },
  { id = "practice.yagni", enabled = false },
]
```

## Writing a practice rule

Here is a whole file. Yours only needs the parts you are changing — the header
is inherited.

```toml
schema = "ringframe.deltas/1"
scope = "practice"
domain = "software-development"
render = { heading = "Rules:", core_cap = 5 }
concerns = ["api_surface", "refactor", "tests_only"]

[[entries]]
id = "practice.task_workflow"
label = "Task workflow"
status = "attributed"
tier = "core"
priority = 10
applies_to = { task = ["plan", "implement"] }
text = """\
For each implementation task, analyze the existing code and acceptance \
criteria; write a failing test, implement the smallest passing change, \
and refactor; then review the diff and resolve findings before advancing. \
In a plan, describe this sequence for each task without executing it. \
In a continuing goal, repeat it until the stated completion criteria \
are met. Use appropriate checks for non-code tasks."""
```

To add that rule to one project, copy just the entry into the project's
`[projects."<path>".ringframe.deltas."practices/software-development"]`
table, alongside any other changes you are making.

**The three fields every rule needs:**

| Field | What it is |
| --- | --- |
| `id` | Its name. Never change it — receipts refer to it. |
| `text` | The instruction. Write something concrete and doable. |
| `applies_to` | When it applies. `{}` means always. |

**The ones that shape how it shows up:**

| Field | What it does |
| --- | --- |
| `label` | The short tag in the `Rules:` line. No commas, colons, or the word "and" — those split a line into two labels. |
| `tier` | `core` = always applies. `situational` (the default) = only when a concern matches. `reference` = never rendered. |
| `priority` | Lower goes first. Default `100`. |
| `concerns` | What this rule is about. **A situational rule with no concerns can never be picked.** |
| `enabled = false` | Turn it off without deleting it. |
| `status` | `attributed` (the default) and `qualified` are used; `candidate` and `retired` are not. |
| `requires.host_capability` | Only `subagents` is understood: skip this rule when the agent has no sub-agents. |

At the top of the file, `description` is one line saying what kind of work this
domain covers. Ask reads it to decide whether the domain applies, so write the
subject matter, not a slogan.

`render` takes two settings. Leave `heading` as `Rules:` — the prompt check
expects it. `core_cap` is how many `core` rules may appear; it defaults to `5`
when a file does not say, and does not limit situational or host rules. The
shipped `software-development` catalog sets `6`, because planning carries one
structural rule about where the plan goes on top of the five principles.

`source`, `why`, and `evidence` are notes for whoever reads the file. They
change nothing.

### Saying when a rule applies

`applies_to` takes up to four lists. **Within one list, any value matches.
Across lists, all of them must.** Leave a list out and it places no restriction.

| List | Matches | Values |
| --- | --- | --- |
| `task` | the classification | `question`, `research`, `clarify`, `plan`, `implement`, `diagnose`, `review`, `operate`, `document` |
| `result` | the classification | `answer`, `plan`, `workspace_change`, `evidence`, `continuing_objective` |
| `effects` | the classification | `read`, `write`, `execute`, `external_effect`, `workspace_read`, `workspace_write`, `external_read` |
| `capability` | the **route** | whichever your profile declares — `native_plan`, `native_goal`, `native_direct`, `native_review` |

So `task = ["plan", "implement"]` means plan **or** implement. Add
`result = ["continuing_objective"]` and now it must be one of those *and* a
continuing objective.

**`task` is what you want; `capability` is how it is being sent, and they are
not the same.** Ask "implement the thing" and it may route through Plan mode to
plan it first — the route says `native_plan` while the task says what the work
is ultimately for. A rule that must hold whenever Plan mode is producing a plan
should therefore key on `capability = ["native_plan"]`, not on `task = ["plan"]`,
which only fires when a plan is the thing you asked for.

There is no `task = "goal"` — a long-running objective is `result =
"continuing_objective"`.

Situational rules need one more thing: a matching **concern**. The `concerns`
list at the top of the file is the whole vocabulary Ask may use. If you add your
own concern in a project, that replaces the list, so copy across the existing
names you still want.

A situational rule whose concern never matches simply never appears, even when
its task fits perfectly. That is the single most common reason a rule you wrote
does not show up.

### Which rules make the cut

For each Ask, the CLI:

1. Throws out rules that are disabled, `candidate` or `retired`, do not match
   `applies_to` — task, result, effects and capability alike — or need
   sub-agents the agent does not have.
2. Splits the rest into **core** and **matching situational**. `reference`
   rules never appear.
3. Sorts each group by `priority`, lowest first, ties broken by file order.
4. Keeps at most `core_cap` core rules, then adds every matching situational
   one. Host rules go above all of them.

**When an Ask names more than one task**, the block is grouped: `Throughout:`
for rules that apply to every named task, then one heading per task in the
order the classification names them. **The cap applies per group**, so an
implementation rule cannot push a research rule out of a research-and-implement
Ask.

**Your rule can lose to the cap.** A new project rule competes with the
inherited core rules: with a cap of five and five inherited rules already at
priority `100`, yours is dropped. Give it `priority = 10` and it goes first —
pushing out the last inherited one instead.

If a rule you wrote is not appearing, check `dropped_by_budget` in the render
output before assuming something is broken. Raising the cap keeps more rules
but makes every prompt longer.

On `status`: your own rules should be `attributed`, which is the default.
`qualified` means somebody measured it, and nothing in the CLI checks that — it
is a note, not a test. `candidate` and `retired` rules are skipped.

`deltas render --statuses qualified,candidate` also shows candidate rules, for
when you are trying something out. It changes nothing about a real Ask.

## Domains: rules for a kind of work

`software-development` is the **base** domain. It always applies.

Any other file in `deltas/practices/` is a **specialist** domain, added *on top*
when the work calls for it. A trading system is still software, so the trading
rules join the engineering rules rather than replacing them.

```sh
ringframe deltas domains --json
```

That lists every domain you have, what each covers, its concerns, and whether
this project opted in. Ask reads exactly that, then adds a specialist domain
when your intent is about that subject or touches its concerns — leaning
towards one the project opted into.

**To opt a project in**, name the domain in an override layer: in Weft,
`[projects."<path>".ringframe.deltas."practices/<domain>"]`, with its
`domain` key. That is all opting in means: a nudge, not a switch. Ask still leaves a specialist domain out
when your request is clearly unrelated.

Each domain gets its own `core_cap`, and the `Rules:` block is base rules first,
then each specialist's. A concern that only a specialist defines is accepted
only while that domain is in play. Naming a domain you do not have stops the Ask
and tells you what you do have — it is never silently ignored.

Every prompt records which domains contributed and what each one added or
dropped.

### Adding a domain

One file in the marketplace's `deltas/practices/<domain>.toml`, or the same keys
under `[ringframe.deltas."practices/<domain>"]` in Weft's `config.toml`. It
needs:

- a `domain` key matching the file name
- a `description` — one line on what work it covers, which is how Ask decides
- a `concerns` list, which is that domain's whole vocabulary

No code changes anywhere. `deltas domains` will find it.

Keep a specialist `core_cap` small. Its core rules stack on top of the base's,
and long prompts get skimmed.

## Writing a host rule

A host rule attaches to one route, by name. No task filters, no concerns.

```toml
schema = "ringframe.deltas/1"
scope = "host"
host = "claude-code"

[[entries]]
id = "claude-code.native_goal.task_workflow"
label = "Task workflow"
status = "candidate"
capability = "native_goal"
text = """\
For each task, analyze the code, implement using TDD, and review the \
change before advancing toward the goal's completion criteria."""
matrix_ref = "https://code.claude.com/docs/en/goal"
```

Each one needs `id`, `capability`, `text`, `matrix_ref`, and `status`. Use
`host = "codex"` and Codex route names for a Codex file.

**The `capability` must be a route the profile actually has.** Check with
`ringframe profile show` — you cannot invent one here. That is the division
again: the profile says what your agent can do, this says what to tell it while
it does that.

Two things to know:

- **Only `qualified` host rules appear.** Everything shipped today is
  `candidate`, so no host rule reaches a prompt by default.
- Practice fields — `priority`, `tier`, `applies_to`, `concerns` — mean nothing
  here. Host rules keep file order.

`matrix_ref` points at the documentation the rule came from. Nothing fetches it.

## Checking your work

Run these inside the project you want to inspect:

```sh
ringframe deltas domains --json
ringframe profile show --host claude-code --json
ringframe deltas render --host claude-code --capability native_plan \
  --classification '{"task":["plan"],"result":"plan","interaction":"approval_gated","horizon":"session","effects":["read"]}'
```

`deltas render` shows what an Ask like that would actually get; add `--json` for
the full picture, including each layer it merged, by name, and what was
dropped for length. These only preview —
nothing is launched, nothing is recorded.

**When a rule does not do what you expected:**

| What you see | Look at |
| --- | --- |
| Your project rule changes nothing | Are you in the right project? Is the filename right? Does the `id` match exactly? |
| It is in `list --effective` but not in the prompt | `status`, `enabled`, the filters, `tier`, `concerns`, and `dropped_by_budget`. |
| Your new rule loses to the shipped ones | Equal priorities keep inherited rules first. Lower its `priority`. |
| "unknown concern" | Your project replaced the `concerns` vocabulary. Copy back the names you still use. |
| It appears in the prompt but reads oddly | The agent applies the rule to your task in its own words. Read the saved `prompt.txt`. |
| It appears, and the agent ignored it anyway | Rules are instructions, not enforcement. Nothing makes an agent obey one. |

That last row is the honest limit. Rules shape what your agent is told.
[Eval](../commands/eval.md) then compares what changed against what you asked
for — but it reads the diff, not the agent's method. Whether a particular rule
changes behaviour is a question for a real experiment, not for this file.
