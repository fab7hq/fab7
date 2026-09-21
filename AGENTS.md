# Fab7 marketplace agent instructions

## GitHub authentication

Before interacting with GitHub, run `gh auth status --active --hostname
github.com`. If `0xnairb` is not the active account, run `gh auth switch
--hostname github.com --user 0xnairb` and verify again. Stop if that account
is unavailable.

## What this repository is

The marketplace for Fab7 plugins, the source of every product's
configuration, and the documentation for both. It contains no application
code. `fab7hq/weft` holds the RingFrame and Weft binaries and nothing else:
no plugins, no profiles, no catalogs.

Documentation lives here rather than beside the code because it describes
configuration and plugins, and this repository is synced rather than built —
a wording fix must not cost a binary release.

## Rules

- A product's `config/` tree must mirror `~/.fab7/<config_home>/config/`
  exactly. Sync is a copy; there is no path translation.
- Only schemas are versioned (`ringframe.bundle/1`, `ringframe.profile/1`,
  `ringframe.deltas/1`). Never add a version range or a minimum CLI version:
  a bundle's `version` is provenance, not a compatibility rule.
- Plugin names are unique across products.
- The repository is released as a whole: tags are `vX.Y.Z`, semver, and cover
  every product. Do not introduce a per-product tag series.
- A practice catalog entry that is `situational` must list `concerns`, or it
  can never be selected. CI enforces this.
- Adding a practice domain is a file in `config/deltas/practices/` with a
  `description`. No code change is needed anywhere.

## Testing a change locally

Both hosts cache an installed plugin by its `version`, so editing a skill here
does not reach an installed plugin until `plugin.json` changes. Do not bump a
version for every edit; remove the installed plugin, the configured marketplace
and the cache, then add this tree back:

```sh
./bin/reinstall-local            # both hosts
./bin/reinstall-local claude     # one host
```

Then restart the host. A running session keeps the skill it loaded at startup,
which is the most common reason an edit appears not to have landed.

Claude Code can also load a plugin straight from the tree for one session,
which picks up edits with `/reload-plugins` and no reinstall:

```sh
claude --plugin-dir "$PWD/products/ringframe/plugins/claude"
```

Bump `plugin.json` and the marketplace entry only when publishing.

## Before tagging

CI must be green: manifests parse, every `source` path exists, plugin names
are unique, every `schema:` is one the current CLI reads, and the catalog
selection tests pass.
