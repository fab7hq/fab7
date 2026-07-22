# Fab7

Fab7 is a small Git-native proof gate for agent-assisted work. It records a
completion claim, runs a verification command itself, and rejects the claim
when its passing evidence no longer matches the repository.

The proof core does not plan work, orchestrate agents, or define a methodology.
The surrounding onboarding layer packages only the thin host skills needed to
reach the deterministic Fab7 CLI.

The repository implements the lean proof gate, released onboarding, and the
`0.2.0` extension-distribution path: catalog refresh, registry or explicit-local
installation, immutable snapshots, native Claude/Codex activation, diagnosis,
and bounded uninstall. Release `0.2.1` adds safe managed-marketplace migration
when Fab7 or an extension changes version. Release `0.2.2` adds generic
`fab7 ext create` source scaffolding plus shared `/fab7:ext-create` and
`$fab7:ext-create` host skills. Muslin is the closure fixture;
[`fab7hq/denim`](https://github.com/fab7hq/denim) remains deferred. See
[`docs/architecture/distribution.md`](docs/architecture/distribution.md); the
onboarding closure record is in
[`docs/plans/onboarding.md`](docs/plans/onboarding.md), and registry work is
tracked in [`docs/plans/ext-registry.md`](docs/plans/ext-registry.md).

Local paths never enter the shared registry and never become runtime links.

## Install

Choose an immutable tag from the
[`fab7hq/fab7` releases](https://github.com/fab7hq/fab7/releases), then replace
`vX.Y.Z` in the command:

```bash
curl -fsSL https://raw.githubusercontent.com/fab7hq/fab7/vX.Y.Z/install.sh | bash
```

The installer derives the selected version from that tagged script and verifies
the matching immutable source archive against its release checksum before
building. Contributors can instead use a reviewed checkout:
`bash install.sh --source .`. Open a new login shell before running `fab7`;
verification and host registration are covered in [`RUNBOOK.md`](RUNBOOK.md).

The registry extension path is:

```bash
fab7 ext refresh
fab7 ext list
fab7 ext create /path/to/extension --name example --publisher owner
fab7 ext build /path/to/extension --host claude
fab7 ext install muslin --host claude  # or: codex
fab7 ext doctor
muslin start --json
fab7 ext uninstall muslin --host claude
```

For explicit local extension development, replace the install command with:

```bash
fab7 ext install --local ../muslin --host claude  # or: codex
```

See [`RUNBOOK.md`](RUNBOOK.md) for the complete new-user journey, expected
global and project layouts, first proof, clone repair, and troubleshooting.

## Create a local extension

Release `0.2.2` includes one generic source scaffold. Run it directly:

```bash
fab7 ext create . --name my-extension --publisher my-org
fab7 ext build . --host claude
```

Or install the Fab7 plugin and invoke the shared host skill:

```text
/fab7:ext-create my-extension
$fab7:ext-create my-extension
```

The command renders one collision-safe, host-neutral `basic` source template.
The skill is a thin workflow over `fab7 ext create`, target-selected
`fab7 ext build --host`, local installation, and diagnosis. Native Claude and
Codex roots come only from Fab7's adapters; the generated extension contains no
host selection, packaging script, or copied host manifest. It does not publish
to the registry or create a GitHub repository. Its three local references are
byte-identical copies of `overview.md`, `distribution.md`, and `ledger.md`; the
Fab7 release builder injects them from `docs/architecture` rather than keeping
a second checked-in copy. The skill loads only the one needed for deeper
guidance and does not fetch those contracts from GitHub. See
[`docs/plans/ext-create.md`](docs/plans/ext-create.md) for the implementation and
release gate.

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
