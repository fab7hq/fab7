# Fab7 GitHub Action

This action builds the Fab7 release from the selected action revision, requires
the consumer's tracked `.fab7/project.json` pin to match it, repairs the ignored
project executable, and then delegates merge decisions to `fab7 ci-check`.

Use checkout history that lets git determine the merge base:

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0
- uses: ./action
  with:
    args: --json
```

The action does not require Claude Code, Codex, or a preinstalled `fab7` binary.
Select an action tag whose Fab7 version and executable digest match the tracked
project contract.
