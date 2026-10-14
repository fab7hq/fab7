# Fab7

The marketplace for Fab7 plugins. Add it once, install any Fab7 product from it.

## What is here

| Path | What it holds |
| --- | --- |
| `products/ringframe/plugins/` | The `rf` plugin: [RingFrame](https://docs.getfab7.com/ringframe/)'s Ask, Eval and Seal inside your coding agent |
| `products/ringframe/config/` | RingFrame's configuration: harness profiles, rules and route rules |
| `products/weft/harnesses/` | What [Weft](https://docs.getfab7.com/weft/) knows of each harness |

Claude Code, Codex, Antigravity and Grok Build are supported.

## Install

Add the marketplace once, then install the plugin:

```sh
# Claude Code
claude plugin marketplace add fab7hq/fab7
claude plugin install rf@fab7

# Codex
codex plugin marketplace add fab7hq/fab7
codex plugin add rf@fab7

# Antigravity has no marketplace to add; it installs from this repository
agy plugin install https://github.com/fab7hq/fab7/tree/main/products/ringframe/plugins/antigravity
```

With [Weft](https://github.com/fab7hq/weft), the `U` view runs these for you.

## Docs

Setting up each harness is at [docs.getfab7.com](https://docs.getfab7.com),
from [fab7hq/docs](https://github.com/fab7hq/docs).

## Releases

Tagged `vX.Y.Z`. A tag covers every product here, so any change — a new rule, a
plugin fix, a new product — is one version bump. It is tagged only when this
repository changes, so it can sit behind [Weft](https://github.com/fab7hq/weft)'s
version. Plugins install from the default branch; a product that reads
configuration from this repository resolves the highest tag.

## License

Apache-2.0. Part of [Fab7](https://getfab7.com).
