---
title: Fab7 uv Migration
type: plan
status: complete
implementation_authorized: true
publication_authorized: true
implementation: complete
publication: released
owner: product-and-engineering
last_updated: 2026-07-25
target_release: v0.4.0
authority_for:
  - host uv prerequisite
  - pinned CPython toolchain
  - native Fab7 build and installation
  - isolated extension dependency and binary builds
  - uv cache and environment ownership
depends_on:
  - docs/product/roadmap.md
  - docs/architecture/distribution.md
  - docs/plans/extension-source-reset.md
---

# Fab7 uv migration

## Outcome

Fab7 `v0.4.0` has one Python toolchain boundary. The host must provide the
`uv` executable before `install.sh` runs. Fab7 recommends the version used by
its release proof but does not enforce that version. It uses the available uv
to install a Fab7-owned standard CPython `3.14.6`, create bounded isolated
build environments, and produce native Fab7 and extension executables. The
installed executables do not import from a mutable virtual environment.

Fab7 shares only immutable or concurrency-safe inputs:

- the host `uv` executable;
- the Fab7-owned CPython `3.14.6` installation; and
- one Fab7-owned uv cache.

Fab7 does not share installed dependency state. Its own build and every
extension build receive a fresh environment. PyInstaller exists only as a
bounded build tool; extension runtime dependencies such as PyYAML are bundled
into the resulting native executable. A successful build retains the closed
package and evidence, not its virtual environment.

This is a breaking distribution migration. It replaces the system-Python
zipapp and pure-Python vendoring directions; it does not add a compatibility
lane for either.

## Fixed toolchain contract

### Hard host prerequisite

`install.sh` requires `uv` on `PATH` before it downloads Python, Fab7 source,
or any dependency. It does not install or upgrade `uv`. Missing or malformed
uv fails before mutation with a stable error and a direct link to the official
uv installer.

`[tool.fab7].recommended-uv-version` records the version exercised by Fab7's
release proof. The bootstrap script and hosted CI carry the same
recommendation. Another syntactically valid uv version emits an advisory and
continues; there is intentionally no `[tool.uv].required-version`,
minimum-version gate, or compatibility range.

Every build records the actual uv path, version, and executable digest. Those
values affect build identity without becoming a host acceptance rule. If a uv
release lacks a command or option Fab7 needs, that operation fails through its
specific Python-install, lock, environment, dependency, or build error. A
later Fab7 release may update the recommendation after proof without turning
it into a prerequisite.

### Pinned Python

The only supported build interpreter is the standard, GIL-enabled CPython
`3.14.6` release. Fab7 invokes `uv python install 3.14.6` with an explicit
Fab7-owned installation directory beneath `FAB7_HOME` and `--no-bin`; uv does
not create its normal managed-Python shim in the user's `~/.local/bin`. Fab7
never selects an ambient project `.venv`, a system interpreter, a
free-threaded `3.14t` build, or a moving `3.14` patch.

After the explicit install step, every later uv command disables implicit
Python downloads and names the installed interpreter directly. The selected
interpreter path, implementation, version, platform, architecture, and
executable digest enter the Fab7 toolchain record.

Python patch upgrades are explicit release work. They update the pin, rebuild
all native artifacts, refresh their identities, pass the complete platform
proof, and ship in a new Fab7 release.

### Shared cache, isolated environments

Fab7 owns one cache beneath `FAB7_HOME/cache/uv/`. All Fab7 and extension
builds use it through an explicit `UV_CACHE_DIR`. The cache is a performance
input only: receipts do not depend on cache presence, cache hits do not bypass
hash verification, and no code edits or deletes cache entries directly.

Every build uses a task-specific directory beneath a bounded Fab7 build root:

```text
~/.fab7/
├── cache/
│   └── uv/
├── toolchains/
│   └── python/
│       └── cpython-3.14.6-<platform>-<arch>/
├── builds/
│   └── <operation-id>/
│       ├── source/
│       ├── builder/.venv/
│       ├── dependencies/
│       ├── work/
│       └── output/
├── runtime/
│   └── <fab7-version>/
└── extensions/
```

The builder `.venv` is never reused by another build. Extension runtime
dependencies are installed into that build's isolated dependency root and
cannot mutate Fab7, another extension, or an earlier build. The shared uv cache
and managed Python make this isolation cheap without creating shared package
state.

Build environments are created with explicit project, configuration, Python,
cache, and output paths. Ambient `VIRTUAL_ENV`, Python path variables, uv/pip
index variables, project configuration, and user site packages do not affect
the build. Conflicting builds may run concurrently because they share only uv's
locked cache; installation and selector mutations remain serialized.

## Fab7 bootstrap and runtime

`install.sh` retains the immutable source archive and checksum boundary, then:

1. validates host uv and advises when it differs from the tested version;
2. resolves and validates `FAB7_HOME` before mutation;
3. downloads and verifies the requested Fab7 source release, or resolves the
   explicit reviewed `--source` checkout;
4. installs standard CPython `3.14.6` beneath the Fab7 toolchain root;
5. creates a fresh isolated builder environment with the repository lock;
6. builds one native `fab7` executable with the Fab7-pinned PyInstaller
   toolchain;
7. builds the complete Claude and Codex host roots from reviewed source;
8. runs the native executable smoke test and validates the complete release;
9. installs the release beneath `runtime/<version>/`; and
10. atomically selects `~/.fab7/bin/fab7`.

The installed release contains the native executable, host roots, and a closed
manifest. It contains no `.venv`, package cache, source checkout, or build
directory. Project initialization can continue copying the self-contained
native executable into `.fab7/bin/fab7`; it does not depend on a global venv or
ambient Python after the copy.

The release manifest adds a generated build identity covering:

```text
uv version
CPython version, implementation, target, and executable digest
PyInstaller and hook lock digest
Fab7 source digest
native executable digest
```

An existing version is immutable. Reinstalling the same version accepts only
an identical release snapshot. A toolchain or executable difference at the
same version fails closed rather than replacing history.

`uv` remains a supported-host prerequisite after installation. Ordinary proof
commands run from the native executable without starting uv, but `fab7 doctor`
reports missing or incompatible uv, and install, upgrade, create, build, and
extension-management operations fail until the prerequisite is restored.

## Extension source and creation

Every new extension is a uv project. Its canonical source is:

```text
fab7-extension.json
pyproject.toml
uv.lock
src/
  extension.py
tests/
skills/
LICENSE                 # optional
```

The schema-1 `fab7-extension.json` remains exactly `schema`, `name`,
`publisher`, and `version`. It does not duplicate dependencies, entrypoints,
hosts, capabilities, toolchain versions, or Fab7 ranges.

`pyproject.toml` owns Python metadata and dependencies:

- `[project] name` and `version` exactly match the Fab7 manifest;
- `requires-python` is `==3.14.*`;
- runtime dependencies live only in `[project].dependencies`; and
- the extension does not choose the Fab7-owned PyInstaller toolchain.

`uv.lock` is mandatory, regular, non-symlinked, current for
`pyproject.toml`, and resolved with CPython `3.14.6`. Both files enter source
identity. Workspaces, editable dependencies, local paths, VCS sources, direct
URLs, private indexes, alternate indexes, and unlocked sources fail closed in
this increment. Dependency installation accepts only hash-verified wheels;
sdist builds remain excluded.

`fab7 ext create` writes the four-field manifest, minimal `pyproject.toml`,
initial `uv.lock`, canonical `src/extension.py`, one standard-library test,
and one canonical start skill. It preflights every output and invokes the
validated host uv only after the source files can be written without
collision. Failure removes only files created by the current operation and
never edits pre-existing project metadata.

The generated test runs in a fresh uv-isolated environment using the locked
project. The `/fab7:ext-create` and `$fab7:ext-create` skills display the exact
source, dependency, test, build, and installation commands and obtain explicit
approval before executing generated code or starting a dependency build.

## Extension build

`fab7 ext build` and the shared local/registry builder use one path:

1. validate the four-field manifest, `pyproject.toml`, `uv.lock`, canonical
   `src/extension.py`, discovered `src/`, `tests/`, and `skills/`, bounds, and
   target hosts;
2. stage only bounded source-owned regular files;
3. derive the source digest before executing build tooling;
4. create a fresh builder `.venv` with CPython `3.14.6`;
5. synchronize the Fab7-owned locked PyInstaller toolchain into the builder;
6. materialize the extension's hash-verified wheel closure into the isolated
   dependency root without modifying the builder or another environment;
7. invoke PyInstaller on `src/extension.py` with only the staged source and
   dependency root on its application search path;
8. reject undeclared outputs, symlinks, unresolved dynamic imports, unbounded
   output, timeout, or a failed native executable smoke test;
9. combine the native executable with the selected Claude and Codex plugin
   roots through the existing host adapters; and
10. emit the closed package and destroy the build environment.

PyInstaller analysis and hooks execute code. A build is therefore stronger
authority than the `v0.3.0` byte-only archive assembly. Direct CLI invocation
is explicit authority; host skills must disclose dependency network access,
hook execution, target platform, and output before asking for approval.
Registry refresh and list remain read-only and never trigger a build.

The native target is generated from the current supported host:

```text
<operating-system>-<architecture>-cpython-3.14.6
```

PyInstaller is not treated as a cross-compiler. Each build produces only the
current native target. The source digest alone is not an install identity; the
build record also covers the target, complete toolchain digest, selected wheel
hashes, native executable digest, selected host roots, and final package
digest.

Two clean builds with the same source, target, and exact toolchain must produce
the same closed package bytes. If PyInstaller cannot meet that gate with fixed
paths, timestamps, environment, and compression, the migration stops before
publication rather than weakening Fab7's deterministic artifact claim.

## Extension installation and lifecycle

The registry publishes reviewed, digest-pinned extension source bundles rather
than moving or prebuilt Python archives. A source bundle contains the exact
canonical source tree and lock, but no environment or generated binary.

`fab7 ext install NAME --host HOST`:

1. resolves one reviewed catalog entry and current native target;
2. downloads and verifies the immutable source bundle;
3. displays the dependency/build authority when invoked through a host skill;
4. builds it through the same isolated path as `fab7 ext build`;
5. validates the generated package and native executable;
6. materializes an immutable target-specific snapshot;
7. atomically selects the executable;
8. activates only the requested native host plugin; and
9. records source, toolchain, target, package, and integration identity.

`fab7 ext install --local` differs only in approved source origin. It uses the
same validation, isolation, native build, package, selection, activation,
rollback, diagnosis, and uninstall code.

Registry installation is no longer an offline unpack operation. It may use a
complete shared cache offline, but otherwise it downloads the exact locked
wheels. Network failure, missing wheel, lock drift, unsupported target,
PyInstaller failure, and smoke-test failure are stable separate errors. No
failed build mutates selected extension or host state.

Installed extensions contain only the native executable, selected host roots,
optional license material, and closed receipt. They do not depend on the
builder venv, extension dependency tree, uv cache, or Python installation at
execution time. Removing the final host integration deletes only that
extension's snapshots; it does not remove the shared cache, Python toolchain,
Fab7 releases, or another extension.

## Plugin boundary

`core/fab7/plugin/` remains native host rendering only. It does not own uv,
Python, dependency resolution, PyInstaller, environments, registry download,
installation, or lifecycle state.

The shared Fab7 action templates change only where user authority and commands
change:

- `ext-create` explains the generated uv project and isolated test/build path;
- `ext-install` distinguishes reviewed source download from native local
  build, discloses network and hook execution, and obtains approval; and
- extension-owned skills still invoke only the installed native extension
  executable.

Claude and Codex adapters continue rendering the same reviewed behavior into
native roots. No host-specific dependency or environment implementation enters
the adapters.

## Authority and exclusions

Implementation was explicitly authorized on 2026-07-24. Publication remains a
later decision after implementation and platform evidence.

The host's `install.sh` invocation authorizes the bounded uv and Python
bootstrap described above. Extension creation writes only its preflighted
source. Extension test, build, local install, and registry source build execute
code and require explicit invocation or host-skill approval. No extension can
mutate Fab7's runtime, toolchain, cache metadata, another build environment, or
another extension.

Excluded from this increment:

- installing or upgrading `uv` for the user;
- a system-Python or no-uv compatibility lane;
- Python other than standard CPython `3.14.6`;
- Windows support before its complete host and lifecycle contract exists;
- a shared mutable venv or persistent per-extension runtime venv;
- sdists, dependency build backends, private or alternate indexes, VCS and
  path dependencies, and editable installs;
- cross-compilation, remote builders, signing, notarization, publication
  automation, or background updates;
- running unreviewed extension builds without explicit authority; and
- compatibility with the retired zipapp dependency-vendoring proposal.

## Implementation sequence

### M1 — Close the toolchain records

- Record one tested uv recommendation in `pyproject.toml` without an enforced
  uv version requirement.
- Add the CPython `3.14.6` and PyInstaller build-tool locks and generated
  manifest fields.
- Define stable missing-tool, invalid-tool, Python-install, environment,
  dependency, native-build, target, and reproducibility errors.
- Add deterministic target and toolchain identity functions before subprocess
  integration.

### M2 — Migrate Fab7 installation

- Make `install.sh` fail closed without valid uv and advise when its version
  differs from the tested recommendation.
- Install CPython `3.14.6` under the resolved `FAB7_HOME`.
- Build Fab7 in a fresh environment and install one native executable.
- Preserve source checksum validation, immutable releases, selector rollback,
  project pinning, PATH ownership, and complete host-root validation.
- Extend `fab7 doctor` to validate the host uv and selected toolchain record.

### M3 — Migrate extension creation

- Add canonical `pyproject.toml` and `uv.lock` templates.
- Make creation transactional across template writes and initial locking.
- Update generated tests, JSON output, host skills, release assets, and creator
  acceptance around isolated uv execution.
- Recreate Muslin from the new creator before using it as proof.

### M4 — Add the isolated native builder

- Add one bounded subprocess seam for uv and PyInstaller.
- Add isolated builder and dependency-root ownership, sanitized environment,
  shared-cache configuration, target derivation, cleanup, and concurrency.
- Replace Python archive assembly with native executable assembly for Fab7
  extensions while retaining canonical source discovery and host adapters.
- Prove PyYAML native-wheel collection and a multi-module
  `src/extension.py` import through the built executable.

### M5 — Migrate registry and installation

- Replace registry package artifacts with immutable source-bundle identity.
- Generate target- and toolchain-bound package and receipt identity locally.
- Reuse one builder for explicit build, local install, and registry install.
- Preserve atomic selection, host migration and rollback, diagnosis, partial
  uninstall, and bounded final deletion.
- Remove superseded zipapp, source-package, catalog, receipt, tests, fixtures,
  and documentation in the same implementation.

### M6 — Close and release

- Update product, architecture, runbook, skills, status, and release guidance.
- Run complete deterministic and platform integration proof.
- Recreate and release Fab7, Muslin, and ext-registry in dependency order only
  after owner authorization.
- Perform fresh network installation and authenticated Claude and Codex
  journeys before asking for publication acceptance.

## Proof and stop condition

Implementation is ready for an owner decision only when:

- missing and malformed uv fail before installer mutation, while a different
  valid version emits an advisory and continues;
- a fresh sandbox with uv but no Python installs the exact standard CPython
  `3.14.6` beneath `FAB7_HOME`;
- ambient Python, `.venv`, uv configuration, indexes, and user packages cannot
  change build identity or output;
- two clean Fab7 native builds and two clean extension native builds match
  byte for byte on each supported target;
- project initialization pins and executes the native Fab7 binary without a
  global venv or system Python;
- two extensions with conflicting dependency versions build concurrently in
  isolated environments while reusing one uv cache;
- PyYAML and the pinned PyInstaller toolchain build into a working extension
  executable, and neither remains as installed extension state;
- source, lock, dependency, target, toolchain, executable, and package changes
  alter the appropriate identities;
- registry and local builds converge on the same package bytes for the same
  source and target;
- failed dependency, build, smoke, host activation, and migration operations
  preserve the prior selected state;
- both Claude and Codex discover, invoke, diagnose, partially uninstall, and
  finally remove recreated Muslin;
- the complete deterministic suite passes with the recommended uv and pinned
  Python;
- hosted macOS and Linux CI pass from clean caches;
- `bash -n install.sh`, Python compilation, documentation links, YAML syntax,
  `git diff --check`, release build, and installed-artifact smoke pass; and
- the owner separately authorizes publication.

Stop when that evidence is recorded. Do not add another environment manager,
runtime service, compatibility parser, index policy, remote builder, or release
automation.

## Current evidence

Documentation review on 2026-07-24 confirmed that uv can install an exact
Python release into an explicitly owned directory, create isolated project
environments, run with a fresh isolated environment, and reuse one
concurrency-safe cache across environments. CPython `3.14.6` is the current
reviewed maintenance release in the pinned series; the
[official release](https://www.python.org/downloads/release/python-3146/)
records its 2026-06-10 publication.

Implementation started on 2026-07-24. An early probe showed that uv `0.6.14`
cannot perform Fab7's CPython `3.14.6` install, while uv `0.11.29` completed
the accepted workflow. Version `0.11.29` is therefore the tested
recommendation, not an acceptance gate. A sandboxed Apple Silicon probe using
that uv release, CPython `3.14.6`, PyInstaller `6.21.0`, and PyYAML `6.0.3`
produced two byte-identical native executables and executed the bundled native
PyYAML module successfully.

Local implementation closed on 2026-07-24. Two extensions with conflicting
`packaging` versions built concurrently against one managed interpreter and uv
cache, executed with their own embedded versions, and left the shared build
root empty. Registry source and explicit local source converged on identical
package bytes. Fresh-home installer tests covered exact managed-Python
bootstrap, idempotence, rollback, rejection of missing or malformed uv before
mutation, and successful installation through a valid non-recommended uv
version. Poisoned ambient Python, venv, uv configuration, and private index
variables did not enter the build, and no managed-Python shim appeared outside
`FAB7_HOME`. The complete deterministic suite uses recommended uv `0.11.29`
and pinned Python `3.14.6`; native release smoke, shell syntax, Python
compilation, and working-tree whitespace checks also pass.

This closed repository implementation, not release acceptance. Ext-registry
migration, immutable publication, release-checksum installation, and
authenticated Claude/Codex journeys remained unperformed and publication was
not authorized.

The real sibling Muslin source was then removed from its active path and
recreated as a fresh repository using native Fab7 `0.4.0` `ext create`.
Root commit `b73f43708bfd52c76c8ba93de7a83ac0d7606d09` owns Muslin `0.2.0`,
which keeps `src/extension.py` as its canonical
entrypoint, imports `src/helper.py`, and declares locked PyYAML `6.0.3` through
its uv project. Its source test passed. Two independent native packages were
byte-identical with package SHA-256
`7cdfa957b276de1ce741c5064e7110afcbc05c15c85ea57241fd6ceed2b00b6a`, and
the executable reported native Fab7 `0.4.0` plus the bundled dependency.
Local installation, diagnosis, execution, partial host uninstall, and final
removal passed with the real Claude and Codex CLIs in an isolated home.

On 2026-07-25, Fab7 commit
`f323c2155f39c3113dc72a36bcf5239a8baa17f6` was pushed normally to `main`.
The reset Muslin `main` was replaced with root commit
`b73f43708bfd52c76c8ba93de7a83ac0d7606d09` through an exact
force-with-lease against the former remote commit. Hosted CI run
[`30113297361`](https://github.com/fab7hq/fab7/actions/runs/30113297361)
passed all `108` tests on clean macOS and Ubuntu runners.

A fresh isolated sandbox cloned both public `main` branches and confirmed the
exact commits. Fab7's reviewed-source installer accepted host uv `0.11.32`
with the `0.11.29` recommendation advisory, installed managed CPython `3.14.6`,
and produced a native Fab7 `0.4.0` installation with no retained venv or
dependency tree. The independently cloned Muslin source then installed into
both real host CLIs through Fab7's local-source path. Diagnosis and execution
passed; Claude Code `2.1.218` and Codex CLI `0.145.0` both discovered enabled
Muslin `0.2.0`, and repeated Codex installation returned `already_installed`.
The target-local package SHA-256 was
`321ae560e09887fc639feb7a29d0f25814bae4f95e871db12e221e0c42d67757`.

The owner then authorized publication. Fab7 `v0.4.0` was released with source
archive SHA-256
`27239cbd59e718f5ff3e735b1f004501cac4f81fe08e82972a3cb45f8750b44a`.
Muslin `v0.2.0` was released with source-bundle SHA-256
`b467f0823c109788be5652263ff4b4fa9eccb9bdf1b18c3a52bd3a7bf5a528a7`,
and ext-registry catalog `0.2.0` published that exact identity.

A fresh isolated home downloaded the immutable Fab7 tag archive and checksum,
installed native Fab7 `0.4.0`, refreshed the public catalog, downloaded and
built released Muslin, activated it in Claude Code `2.1.218` and Codex CLI
`0.145.0`, passed diagnosis and execution, and returned
`already_installed` on repeat installation. The target-local package SHA-256
was `f8ec1b798f78abb4fa847d43eedbc386b1ccab582db35e840dce84877e940b72`.
No authenticated model session invoked the released skills; native host
discovery and the deterministic release path were observed directly.
