# Fab7 new-user onboarding runbook

This runbook takes a new user through the smallest complete Fab7 path:

1. install Fab7 once for the user under `~/.fab7/`;
2. register Fab7 with Claude Code or Codex CLI;
3. initialize one Git repository under `<repo>/.fab7/`; and
4. record and verify one completion claim.

Fab7 currently supports macOS or Linux, Bash or Zsh, Git, and Python 3.11 or
newer. Windows, other shells, and Denim are outside this path. Release `v0.2.0`
adds registry and explicit-local extension distribution; release `v0.2.1`
adds safe managed-marketplace migration across versions; and release `v0.2.2`
adds generic extension creation and target-specific builds.

## Current release status

`v0.2.2` is the current Fab7 release. Its installer verifies the matching
GitHub tag archive against the release checksum asset before building. Release
`v0.1.0` established the onboarding path, which the owner accepted on
2026-07-20 after source and network verification; exact platform and host
transcripts were not retained.

The released `v0.2.1` artifact migrated existing `v0.2.0` registrations in
fresh isolated Codex and Claude homes; repeated registration was idempotent.

The released `v0.2.2` artifact adds generic `fab7 ext create` plus shared
`ext-create` skills for Claude and Codex. Its immutable network installation,
registry refresh, and Muslin `v0.1.1` installation passed in both hosts.

The exact implementation evidence and closure limits live in
[`docs/plans/onboarding.md`](docs/plans/onboarding.md#current-implementation-evidence).

## 1. Check prerequisites

Run:

```bash
git --version
python3 --version
printf '%s\n' "$SHELL"
```

Confirm Python is 3.11 or newer and the shell ends in `bash` or `zsh`. Install
and authenticate at least one supported agentic CLI before host registration:

```bash
claude --version
# or
codex --version
```

## 2. Install Fab7 for the user

### Immutable `v0.2.2` release

Installation is one command:

```bash
curl -fsSL https://raw.githubusercontent.com/fab7hq/fab7/v0.2.2/install.sh | bash
```

The installer fetches the matching GitHub tag archive and release checksum,
verifies the source, builds the executable, and changes the shell startup file
only after installation succeeds.

Then open a new login shell and verify the selected global executable:

```bash
exec "$SHELL" -l
command -v fab7
fab7 --version
```

The command path should resolve to `~/.fab7/bin/fab7`. Re-running the same
version is idempotent.

### Reviewed source checkout

Contributors can instead clone or open a checkout they trust and install from
that source:

```bash
git clone https://github.com/fab7hq/fab7.git
cd fab7
bash install.sh --source .
exec "$SHELL" -l
fab7 --version
```

## 3. Register one agentic CLI

Choose one host. The command installs the bundled `fab7@fab7` plugin in the
host's user scope and is safe to rerun.

### Claude Code

```bash
fab7 install claude --json
claude plugin list --json
```

Open Claude Code:

```bash
claude
```

Then reload plugins inside the session before first use:

```text
/reload-plugins
```

### Codex CLI

```bash
fab7 install codex --json
codex plugin list --json
```

Start a new Codex CLI session after installation. Bundled skills are loaded at
session start:

```text
codex
```

The structured install result must report `installed`, `already_installed`, or
`migrated`. A migration means Fab7 replaced a validated older marketplace from
the same managed home. If it reports an error, stop before project
initialization and use the troubleshooting table below.

## 4. Initialize a project

Enter a Git repository with at least one commit:

```bash
cd /path/to/project
git rev-parse --show-toplevel
git rev-parse --verify HEAD
```

Initialize from the selected host:

| Host | Prompt command |
|---|---|
| Claude Code | `/fab7:init` |
| Codex CLI | `$fab7:init` |

The host component delegates to `fab7 init --json`. You can run the same
operation directly from the shell:

```bash
fab7 init --json
```

Track the project contract before recording evidence:

```bash
git add .fab7/project.json .fab7/.gitignore
git commit -m "Initialize Fab7"
```

The resulting ownership boundary is:

```text
~/.fab7/                         # user-global, never committed
├── bin/
│   └── fab7                    # selected executable
└── runtime/
    └── <installed-version>/
        ├── manifest.json
        ├── bin/fab7
        └── hosts/
            ├── claude/
            └── codex/

<repo>/.fab7/                   # project-local
├── project.json               # tracked version and executable digest
├── .gitignore                 # tracked; ignores only /bin/
├── records/                   # tracked append-only proof records
└── bin/
    └── fab7                    # ignored copy of the pinned executable
```

Check that Git ignores only the generated executable:

```bash
git check-ignore .fab7/bin/fab7
git status --short
```

## 5. Record the first proof

Commit the implementation you want to verify first. `fab7 verify` rejects
uncommitted non-record changes.

```bash
fab7 claim --work-item onboarding --summary "Onboarding is complete"
```

Copy the printed `rec_...` claim ID into the verification command:

```bash
fab7 verify \
  --work-item onboarding \
  --claim rec_REPLACE_ME \
  -- python -m pytest

fab7 ci-check --work-item onboarding
fab7 audit --work-item onboarding
fab7 doctor
```

Replace `python -m pytest` with the repository's real deterministic test
command. A passing command alone is not enough: `ci-check` also requires linked
evidence for the latest claim and rejects evidence made stale by later code
changes. Commit the appended `.fab7/records/onboarding.jsonl` with the work it
proves.

## 6. Repair after cloning

The generated `.fab7/bin/fab7` is intentionally not committed. On a new clone,
install the version pinned in `.fab7/project.json` globally, then run:

```bash
fab7 init --json
```

Initialization preserves the tracked pin and all records while repairing only
the ignored executable. It does not silently change a project's Fab7 version.

## Troubleshooting

| Symptom or code | Action |
|---|---|
| `fab7: command not found` | Run `exec "$SHELL" -l`, then confirm `~/.fab7/bin` is on `PATH`. |
| `FAB7_GLOBAL_NOT_INSTALLED` | Run the installation step before `fab7 init` or host registration. |
| `FAB7_HOST_MISSING` | Install the selected host CLI and confirm `claude` or `codex` is on `PATH`. |
| `FAB7_HOST_MARKETPLACE_CONFLICT` | The same name points outside the exact managed Fab7 family or its surviving artifacts are invalid. Inspect `claude plugin marketplace list --json` or `codex plugin marketplace list --json`; do not overwrite it blindly. |
| Fab7 points to an older managed runtime | Install `v0.2.2` or newer, then rerun `fab7 install HOST`; a validated same-family registration reports `migrated`. If the conflict remains, inspect it as an unrelated or invalid marketplace. |
| Plugin installed but command is absent | In Claude Code run `/reload-plugins`. For Codex, exit and start a new CLI session. |
| `FAB7_PROJECT_NOT_INITIALIZED` | Run `fab7 init --json` inside the Git repository. |
| `FAB7_PROJECT_EXECUTABLE_INVALID` | Run `fab7 init --json` to repair the ignored executable from the pinned global release. |
| `FAB7_PROJECT_PIN_INVALID` | Do not edit `project.json` manually. Install the pinned release or restore the tracked contract. |
| `FAB7_REPOSITORY_DIRTY` | Commit or remove non-record changes, then run verification again. |

Use `--json` when capturing an error for support; Fab7 preserves stable error
codes in the structured response. Do not place credentials, host transcripts,
or unrelated tool output under `~/.fab7/` or `.fab7/`.

## Extension distribution

Refresh and list the reviewed registry:

```bash
fab7 ext refresh --json
fab7 ext list --json
fab7 ext install muslin --host claude --json
# or: --host codex
fab7 ext doctor --json
muslin start --json
```

For local extension development, inspect the source manifest before granting
its bounded build, then replace the name-based install with:

```bash
fab7 ext install --local /path/to/muslin --host claude --json
# or: --host codex
fab7 ext doctor --json
muslin start --json
```

Install into the second host by repeating the same source command with the
other host. Uninstall removes only the named integration until the final host:

```bash
fab7 ext uninstall muslin --host claude --json
fab7 ext uninstall muslin --host codex --json
```

The registry contains only release URLs and digests. Local paths are explicit,
never enter the shared catalog, and produce immutable development snapshots.

## Create an extension

After installing this reviewed checkout, create source directly in an existing
non-symlink directory:

```bash
fab7 ext create /path/to/extension \
  --name my-extension \
  --publisher my-org \
  --json
```

Creation is host-neutral. The command uses the installed Fab7 version as the
minimum and refuses to replace any generated path.

The registered host skills delegate to the same command:

```text
/fab7:ext-create my-extension
$fab7:ext-create my-extension
```

Before running generated code, the skill displays the exact test, target build,
and install commands plus the declared source files, then asks for explicit
approval. The accepted path creates a deterministic ZIP through only the
selected adapters, installs the same schema-2 source, and runs diagnosis.

The standalone build command requires one or more target hosts and defaults to
the current folder and a new target-qualified ZIP:

```bash
fab7 ext build --host claude --json
# or
fab7 ext build /path/to/extension \
  --host claude \
  --host codex \
  --output /path/to/extension.zip \
  --json
```

Without `--output`, the path is
`dist/<name>-<version>-<target[-target...]>.zip`. The command reports its target
list plus source and artifact SHA-256 digests and refuses to replace an existing
output. It builds only; it does not install or publish the extension.

For deeper onboarding, ask the skill about architecture, the extension
contract, or proof and authority. It reads only the matching local reference
and maps each generated file to the core/extension separation, deterministic
package lifecycle, proof boundary, and retained human decisions.

After success:

```text
/reload-plugins
/my-extension:start
```

This is local extension development only. Registry submission, release,
repository creation, and CI generation are outside the skill.

Fab7's own Claude and Codex plugins are built from shared action sources and the
same focused adapter modules used by schema-2 extension builds. To inspect a
complete release and its rendered host artifacts, use a new output path:

```bash
PYTHONPATH=core python3 -m fab7.release_build --release-root <new-directory>
claude plugin validate --strict <new-directory>/hosts/claude
```

There is no source `scripts/` directory. `install.sh` executes this core module
with the reviewed source on `PYTHONPATH`, so it can bootstrap the executable
before Fab7 is installed. Core owns generic scaffolding and adapter assembly.
The module does not install rendered roots or claim unsupported hosts.

## Reference

- [`docs/architecture/distribution.md`](docs/architecture/distribution.md)
  owns the global and project layouts, release contract, and host boundary.
- [`docs/architecture/ledger.md`](docs/architecture/ledger.md) owns proof-record
  behavior and freshness.
- [`docs/plans/onboarding.md`](docs/plans/onboarding.md) owns current evidence,
  open gates, and phase closure.
