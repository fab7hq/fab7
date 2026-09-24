# RingFrame in Codex

## Before you start

- Install the [RingFrame CLI](https://github.com/fab7hq/weft#install).
- Install and sign in to [Codex](https://developers.openai.com/codex/cli/).
- Make sure `ringframe` is on the PATH that Codex uses.
- Turn on native sub-agent tools — Eval needs them — and allow the plugin to
  read and write files and run `ringframe`.

Ask and Seal need Codex's `request_user_input` chooser to ask you anything, so
use a mode that offers it. If your Codex has the feature flag, you can turn it
on in Default mode:

```sh
codex features enable default_mode_request_user_input
```

RingFrame will not change your Codex settings for you.

## Install the plugin

```sh
codex plugin marketplace add fab7hq/fab7
codex plugin add rf@fab7
```

Start a new session in your project, then open `/hooks`, look at the `rf@fab7`
prompt hook, and trust it. **Installing the plugin and trusting its hook are two
separate steps** — the hook is what records that you submitted a prompt, so
without it you lose that evidence.

RingFrame sets a project up the first time you use it, including when it sits
inside a bigger Git repository.

## Using it

Type these as you work:

```text
$rf:ask add a health endpoint with tests
$rf:eval use native sub-agents
$rf:seal accepted
```

**Ask** picks a route, then shows you the whole prompt. You can go ahead, change
it, run it directly instead, or cancel.

On Codex you submit the prompt yourself: Ask gives you the saved prompt for
`/plan`, `/goal`, or `/review`. Direct execution just carries on in the same
turn. You never have to name a route — say what you want.

Then work normally.

**Eval** — say `use native sub-agents` every time, as above. That is what
authorises Codex to spawn the reviewers, and it is needed even when sub-agent
tools are already on. `$rf:eval` by itself is not enough.

An agent maps the diff, then four judges: one works out what was actually
promised, three check coverage, drift, and what is being glossed over. You get
what is missing, what changed that nobody asked for, and how much they agreed.
It reads the diff; it does not run your tests. Give any of them a model and an
effort (`$rf:eval use native sub-agents drift=gpt-6-sol/high`), or gather here
and debate elsewhere (`$rf:eval gather`): see
[stages, models and efforts](../commands/eval.md#stages-models-and-efforts).

**Seal** asks you to confirm, then closes the open Asks: `accepted`, `rejected`,
`deferred`, or `abandoned`, with a note if you want one. You can Seal with or
without an Eval.

Details: [Ask](../commands/ask.md), [Eval](../commands/eval.md),
[Seal](../commands/seal.md).

## Updating

Run the [installer](https://github.com/fab7hq/weft#install) again for the CLI, then:

```sh
codex plugin marketplace upgrade fab7
codex plugin add rf@fab7
```

Start a new session, and check `/hooks` again if the hook changed.

## Your rules and your records

[Change the rules](../architecture/delta.md) for yourself or for one project.

RingFrame uses whatever project directory Codex reports, and never moves records
afterwards. From that directory:

```sh
ringframe ask list --json
ringframe eval list --json
ringframe ledger verify --json
```

**If Ask or Seal cannot ask you anything**, `request_user_input` is not
available in your current mode.

**If Eval says it reviewed in shared context**, sub-agent tools were not
available, so the judges saw each other's answers. The verdict still stands,
but they were not independent.

**If nothing works**, run `ringframe --version` in the same shell you launch
Codex from — the plugin calls the CLI, and it has to be findable.
