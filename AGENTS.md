# Fab7 Development Guidance

This file defines the repository-wide engineering philosophy for Fab7. It is
independent of any fabric, feature, phase, or delivery increment.

Accepted product and architecture documents remain authoritative. Apply them
with the lean, clean, and concise rules below.

## Principles

### Build the smallest complete path

Prefer one narrow path from accepted input to user-visible outcome over broad,
partially connected infrastructure. Stop when the accepted outcome is met. Do
not add adjacent features, future stages, compatibility layers, services,
dashboards, extension systems, or configuration without a current need.

### Keep a small deterministic spine

Use deterministic code for validation, identity, authority, state transitions,
evidence, and finite outcomes. Prefer a function or small module over a
framework, registry, manager hierarchy, or indirection that enforces no real
boundary.

AI may interpret, research, create, review, and recommend. Its output is a
proposal or observation—not accepted state, authority, proof, or self-
certification.

### Put evidence before claims

Completion messages, process exits, and review prose are not proof by
themselves. Claims require current, linked, scope-matching evidence. Missing,
failed, stale, ambiguous, or mismatched evidence fails closed.

Reconstruct durable state from repository-owned records and Git, not chat
history, private reasoning, or ambient memory. Never retain secrets, raw
transcripts, chain-of-thought, or unrelated tool output.

### Default to least privilege

Effective authority is the intersection of accepted scope, policy, runtime
capability, repository restrictions, and explicit human grant. Missing or
malformed authority means denied; authority booleans are literal and default to
`false`.

Material scope, new authority, irreversible action, production mutation,
spend, external exposure, residual-risk acceptance, merge, release, deployment,
and retained-memory promotion remain explicit human decisions.

### Make complexity earn its place

Every module, role, skill, adapter, record, hook, policy, process, dependency,
and option must solve a named current need. If its value cannot be tied to an
accepted outcome in one sentence, do not add it.

Prefer direct composition. Extract shared machinery only after a real repeated
contract appears. Small duplication is often cheaper than a premature
abstraction.

### Preserve one-way boundaries

Fab7 core remains host-neutral and fabric-neutral. Fabrics and host packages
may depend on public Fab7 contracts; core must not depend on a fabric, provider,
or host runtime. Cross boundaries through public interfaces rather than
imports, vendoring, or shared mutable internals.

### Prefer closed records and explicit transitions

Use small, versioned, validated records with clear ownership. Deterministic
code derives identifiers, digests, and transition metadata. Transitions have
explicit preconditions, one bounded effect, stable failures, and a finite
result. Reject ambiguity; append repair instead of rewriting accepted history.

Preserve unrelated user work. Bound paths, commands, subprocess time, and
retained output. Isolate risky changes, serialize conflicting mutations, and
reject dirty, out-of-scope, stale, or ambiguous state.

### Test stable behavior

Automate deterministic contracts and executable boundaries: Python modules,
schemas, CLI envelopes, public APIs, subprocesses, launchers, Git safety,
timeouts, concurrency, evidence rules, packaging, drift, and one minimal end-
to-end path for each implementation claim.

Do not use comparative LLM evaluation, repeated model trials, prompt/reviewer
scores, story matrices, fake live-host drivers, operator-gated suites, or
token/cost benchmarks as ordinary regression tests. Use one bounded manual
observation only when a requirement makes a specific model or host claim.

Prefer distinct contractual coverage over test counts. Delete duplicate tests.

### Delete and reconcile completely

Generated output is derived: change reviewed source or generic builders, then
rebuild and check byte/mode drift. Never make generated files the only source
of a change.

When scope shrinks or a design is replaced, remove obsolete runtime, tests,
fixtures, configuration, contracts, dependencies, generated output, and active
documentation together. Keep useful history as short decision context, not
dormant machinery or authority.

### Close finitely and truthfully

Define outcome, exclusions, proof, budget, stop rules, and human decisions
before implementation. At closure record what passed, failed, or was not run;
the residual limits; the exact human decision; and one next action.

Implementation completion, evidence readiness, merge, release, and deployment
are separate states. Never turn an unperformed check into passing evidence or
leave a retired gate ambiguously active.

## Working Method

Before editing:

1. Read the authoritative product and architecture documents.
2. Inspect current code and tests before proposing structure.
3. State the smallest outcome, non-goals, public entry point, authority, proof,
   and finite stop condition.
4. Reuse an existing mechanism unless it cannot meet a named requirement.

While implementing:

1. Add a failing test for deterministic runtime or contract changes.
2. Implement the thinnest complete path.
3. Keep functions focused, names literal, data flow visible, and errors stable.
4. Prefer the standard library and existing utilities over dependencies.
5. Delete superseded code in the same change and preserve unrelated work.

While reviewing, ask:

- Can this be deleted or be a function instead of a framework?
- Is authority wider, state more implicit, or proof weaker than necessary?
- Does each test protect a distinct deterministic contract?
- Does documentation claim more than the implementation proves?

## Verification

Use focused deterministic tests during development. For shared runtime changes:

```bash
uv run python -m pytest
```

Documentation-only work needs structure, link, format, and status-consistency
checks—not model evaluation.

## Documentation

One fact has one authoritative owner: product owns outcomes; architecture owns
system shape and implemented contracts; `docs/README.md` routes readers; and
`docs/status.yaml` points to the complete current set.

Update affected authorities together, but do not repeat long explanations.
Prefer a short rule and a link. Keep historical rationale in Git rather than
adding active documentation categories or stale references.

## Repository Conventions

- Search with `rg` or `rg --files`.
- Use `apply_patch` for hand-authored edits.
- Preserve unrelated changes in a dirty worktree.
- Run `git diff --check` before handoff.
- Add no dependency, process, service, or abstraction without an accepted need.

Use Context7 for current documentation about a library, framework, SDK, API,
CLI, or cloud service: resolve its library ID first, then query the full,
concept-focused question. It is unnecessary for repository-local refactoring,
business logic, code review, or scripts written from first principles.
