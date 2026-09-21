# RingFrame in Claude Code

## Before you start

- Install the [RingFrame CLI](https://github.com/fab7hq/weft#install).
- Install and sign in to [Claude Code](https://code.claude.com/docs/en/setup).
- Make sure `ringframe` is on the PATH that Claude Code uses.
- Allow the plugin the tools it needs: asking you questions, reading and writing
  files, running `ringframe`, and spawning agents. Eval uses four of them.

## Install the plugin

```sh
claude plugin marketplace add fab7hq/fab7
claude plugin install rf@fab7
```

That installs it for you, everywhere. To install it for one project instead,
run `claude plugin install rf@fab7 --scope project` from that project. See
Claude's [plugin reference](https://code.claude.com/docs/en/plugins-reference#plugin-install).

Start a new session in your project. RingFrame sets that project up the first
time you use it — including when it sits inside a bigger Git repository.

## Using it

Type these as you work:

```text
/rf:ask add a health endpoint with tests
/rf:eval
/rf:seal accepted
```

**Ask** picks a route, then shows you the whole prompt. You can go ahead,
change it, run it directly instead, or cancel. Say yes and Plan mode opens with
the prompt in it; direct execution just carries on in the same turn. For a
long-running Goal, Ask hands you the saved prompt to submit yourself.

You never have to name a route. Say what you want.

Then work normally — implement, revise, argue with your agent.

**Eval** looks at everything still open and asks four judges: one works out
what was actually promised, three check coverage, drift, and what is being
glossed over. You get what is missing, what changed that nobody asked for, and
how much they agreed.

It reads the diff. It does not run your tests.

**Seal** asks you to confirm, then closes the open Asks: `accepted`,
`rejected`, `deferred`, or `abandoned`, with a note if you want one. You can
Seal with or without an Eval.

Details: [Ask](../commands/ask.md), [Eval](../commands/eval.md),
[Seal](../commands/seal.md).

## Updating

Run the [installer](https://github.com/fab7hq/weft#install) again for the CLI, then:

```sh
claude plugin marketplace update fab7
claude plugin update rf@fab7
```

Add `--scope project` if you installed it that way. Restart Claude Code to pick
up the new plugin.

## Your rules and your records

[Change the rules](../architecture/delta.md) for yourself or for one project.

RingFrame uses whatever project directory Claude Code reports, and never moves
records afterwards. From that directory:

```sh
ringframe ask list --json
ringframe eval list --json
ringframe ledger verify --json
```

**If `/rf:ask` does not appear**, check the plugin is enabled in `/plugin` and
start a new session.

**If it appears but fails**, run `ringframe --version` in the same shell you
launch Claude Code from — the plugin calls the CLI, and it has to be findable.
