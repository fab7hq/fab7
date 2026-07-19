# Fab7

Fab7 is a small Git-native proof gate for agent-assisted work. It records a
completion claim, runs a verification command itself, and rejects the claim
when its passing evidence no longer matches the repository.

The proof core does not plan work, orchestrate agents, or define a methodology.
The surrounding onboarding layer packages only the thin host skills needed to
reach the deterministic Fab7 CLI.

The repository implements the lean proof gate plus the local-source onboarding
spine: a deterministic release builder, `install.sh`, explicit
`fab7 install claude|codex` registration, and a version-pinned project
installation beneath `.fab7/`. Network-release and Linux acceptance remain
open. Extension distribution through
[`fab7hq/ext-registry`](https://github.com/fab7hq/ext-registry) and the first
extension, [`fab7hq/denim`](https://github.com/fab7hq/denim), are deferred.
See [`docs/architecture/distribution.md`](docs/architecture/distribution.md);
the remaining delivery gates are in
[`docs/plans/onboarding.md`](docs/plans/onboarding.md).

## Install

```bash
curl -fsSLo /tmp/fab7-install-v0.1.0.sh \
  https://raw.githubusercontent.com/fab7hq/fab7/v0.1.0/install.sh
bash /tmp/fab7-install-v0.1.0.sh --version 0.1.0
exec "$SHELL" -l
fab7 --version
fab7 install claude  # or: fab7 install codex
```

The installer verifies the immutable `v0.1.0` source archive against its
release checksum before building. Contributors can instead use the reviewed
checkout path: `bash install.sh --source .`.

See [`RUNBOOK.md`](RUNBOOK.md) for the complete new-user journey, expected
global and project layouts, first proof, clone repair, and troubleshooting.

## Complete path

```bash
fab7 init
git add .fab7/project.json .fab7/.gitignore
git commit -m "Initialize Fab7"
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

From Claude Code use `/fab7:init`; from Codex use `$fab7:init`. The installed
host component delegates to the same `fab7 init --json` command. Claude needs
`/reload-plugins` after first installation; Codex needs a new session.

## Development

```bash
uv sync --python 3.12
uv run python -m pytest
git diff --check
```

Product direction, architecture, and status begin at
[`docs/README.md`](docs/README.md). Repository engineering guidance lives in
[`AGENTS.md`](AGENTS.md).
