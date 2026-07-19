# Fab7

Fab7 is a small Git-native proof gate for agent-assisted work. It records a
completion claim, runs a verification command itself, and rejects the claim
when its passing evidence no longer matches the repository.

The implemented proof core does not plan work, orchestrate agents, define a
methodology, or package host-specific plugins.

The current repository implements only this lean proof gate. The accepted next
phase adds a repository-owned bootstrap script and explicit
`fab7 install claude|codex` host registration. The bootstrap creates the
user-global `~/.fab7/` installation; the future `fab7 init` creates a
version-pinned project installation beneath `.fab7/` without moving host
behavior into the proof core. Extension distribution through
[`fab7hq/ext-registry`](https://github.com/fab7hq/ext-registry) and the first
extension, [`fab7hq/denim`](https://github.com/fab7hq/denim), are deferred.
See [`docs/architecture/distribution.md`](docs/architecture/distribution.md);
those commands are not implemented yet. The draft delivery sequence is in
[`docs/plans/onboarding.md`](docs/plans/onboarding.md).

## Install

```bash
uv tool install .
fab7 --version
```

## Complete path

```bash
fab7 init
fab7 claim --work-item pr-1 --summary "Implementation complete"

# Use the claim id printed above.
fab7 verify --work-item pr-1 --claim rec_... -- python -m pytest
fab7 ci-check --work-item pr-1
fab7 audit --work-item pr-1
fab7 doctor
```

`verify` requires the non-Fab7 working tree to be clean. It executes the argv
after `--` without a shell, records the exit code and output digest, and binds
the observation to the current Git commit. `ci-check` passes only when the
latest claim has linked, passing evidence and no implementation file changed
after that evidence was captured.

## Development

```bash
uv sync --python 3.12
uv run python -m pytest
git diff --check
```

Product direction, architecture, and status begin at
[`docs/README.md`](docs/README.md). Repository engineering guidance lives in
[`AGENTS.md`](AGENTS.md).
