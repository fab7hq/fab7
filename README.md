# Fab7

The marketplace for Fab7 plugins. Add it once, install any Fab7 product from it.

## Claude Code

```sh
claude plugin marketplace add fab7hq/fab7
claude plugin install <plugin>@fab7
```

## Codex

```sh
codex plugin marketplace add fab7hq/fab7
codex plugin add <plugin>@fab7
```

## What is here

| Plugin | Product | Hosts | Setup |
| --- | --- | --- | --- |
| `rf` | [RingFrame](https://docs.getfab7.com/ringframe/) — Ask, Eval, and Seal inside your coding agent | Claude Code, Codex | [Install](https://docs.getfab7.com/fab7/), then [set up your harness](https://docs.getfab7.com/ringframe/harnesses/) |

Every product is documented at [docs.getfab7.com](https://docs.getfab7.com), from
[fab7hq/docs](https://github.com/fab7hq/docs).

## Releases

Tagged `vX.Y.Z`. A tag covers every product here, so any change — a new rule, a
plugin fix, a new product — is one version bump. Plugins install from the
default branch; a product that reads configuration from this repository
resolves the highest tag.

Apache-2.0.
