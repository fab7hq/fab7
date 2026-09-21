# Fab7

The marketplace for Fab7 plugins. Add it once, install any Fab7 product from it.

## Claude Code

```sh
/plugin marketplace add fab7hq/fab7
/plugin install <plugin>@fab7
```

## Codex

```sh
codex plugin marketplace add fab7hq/fab7
codex plugin add <plugin>@fab7
```

## What is here

| Plugin | Product | Hosts | Setup |
| --- | --- | --- | --- |
| `rf` | [RingFrame](products/ringframe/docs/product.md) — Ask, Eval, and Seal inside your coding agent | Claude Code, Codex | [install the CLI](https://github.com/fab7hq/weft#install) |

Each product is documented under `products/<name>/docs/`.

## Releases

Tagged `vX.Y.Z`. A tag covers every product here, so any change — a new rule, a
plugin fix, a new product — is one version bump. Plugins install from the
default branch; a product that reads configuration from this repository
resolves the highest tag.

Apache-2.0.
