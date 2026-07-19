# Fab7 new-user onboarding runbook

This runbook takes a new user through the smallest complete Fab7 path:

1. install Fab7 once for the user under `~/.fab7/`;
2. register Fab7 with Claude Code or Codex CLI;
3. initialize one Git repository under `<repo>/.fab7/`; and
4. record and verify one completion claim.

Fab7 currently supports macOS or Linux, Bash or Zsh, Git, and Python 3.11 or
newer. Windows, other shells, extension discovery, `ext-registry`, and Denim are
not part of this onboarding path.

## Current release status

`v0.1.0` is the first tagged Fab7 release. Its installer verifies the matching
GitHub tag archive against the release checksum asset before building. Network
installation and Linux acceptance remain release gates until they have fresh
operator evidence.

Local-source plugin registration has been accepted by both host CLIs. Fresh
authenticated invocation of `/fab7:init` and `$fab7:init` remains an open
gate for the exact released artifact.

The exact implementation evidence and remaining release gates live in
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

### Available now: reviewed source checkout

Clone or open a checkout you trust, then install from it:

```bash
git clone https://github.com/fab7hq/fab7.git
cd fab7
bash install.sh --source .
exec "$SHELL" -l
```

Verify the selected global executable:

```bash
command -v fab7
fab7 --version
```

The command path should resolve to `~/.fab7/bin/fab7`, and the current source
reports version `0.1.0`. Re-running the same install is idempotent.

### Immutable `v0.1.0` release

Download the installer from the exact tag, review it, and run it with the exact
version:

```bash
curl -fsSLo /tmp/fab7-install-v0.1.0.sh \
  https://raw.githubusercontent.com/fab7hq/fab7/v0.1.0/install.sh
less /tmp/fab7-install-v0.1.0.sh
bash /tmp/fab7-install-v0.1.0.sh --version 0.1.0
exec "$SHELL" -l
fab7 --version
```

The installer fetches the matching GitHub tag archive and release checksum,
verifies the source, builds the executable, and changes the shell startup file
only after installation succeeds.

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

The structured install result must report `installed` or
`already_installed`. If it reports an error, stop before project initialization
and use the troubleshooting table below.

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
    └── 0.1.0/
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
| `FAB7_HOST_MARKETPLACE_CONFLICT` | A different source already owns the `fab7` marketplace name. Inspect `claude plugin marketplace list --json` or `codex plugin marketplace list --json`; do not overwrite it blindly. |
| Plugin installed but command is absent | In Claude Code run `/reload-plugins`. For Codex, exit and start a new CLI session. |
| `FAB7_PROJECT_NOT_INITIALIZED` | Run `fab7 init --json` inside the Git repository. |
| `FAB7_PROJECT_EXECUTABLE_INVALID` | Run `fab7 init --json` to repair the ignored executable from the pinned global release. |
| `FAB7_PROJECT_PIN_INVALID` | Do not edit `project.json` manually. Install the pinned release or restore the tracked contract. |
| `FAB7_REPOSITORY_DIRTY` | Commit or remove non-record changes, then run verification again. |

Use `--json` when capturing an error for support; Fab7 preserves stable error
codes in the structured response. Do not place credentials, host transcripts,
or unrelated tool output under `~/.fab7/` or `.fab7/`.

## Reference

- [`docs/architecture/distribution.md`](docs/architecture/distribution.md)
  owns the global and project layouts, release contract, and host boundary.
- [`docs/architecture/ledger.md`](docs/architecture/ledger.md) owns proof-record
  behavior and freshness.
- [`docs/plans/onboarding.md`](docs/plans/onboarding.md) owns current evidence,
  open gates, and phase closure.
