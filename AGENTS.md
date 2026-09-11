# Fab7 marketplace agent instructions

## GitHub authentication

Before interacting with GitHub, run `gh auth status --active --hostname
github.com`. If `0xnairb` is not the active account, run `gh auth switch
--hostname github.com --user 0xnairb` and verify again. Stop if that account
is unavailable.

## What this repository is

The marketplace for Fab7 plugins, and the source of every product's
configuration. It contains no application code. `fab7hq/ringframe` holds the
RingFrame CLI and nothing else: no plugins, no profiles, no catalogs.

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

## Before tagging

CI must be green: manifests parse, every `source` path exists, plugin names
are unique, every `schema:` is one the current CLI reads, and the catalog
selection tests pass.
