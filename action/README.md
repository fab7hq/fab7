# Fab7 GitHub Action

This action installs the host-neutral Fab7 CLI from this repository checkout and
then delegates merge decisions to `fab7 ci-check`.

Use checkout history that lets git determine the merge base:

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0
- uses: ./action
  with:
    args: --json
```

The action does not require Claude Code or a preinstalled `fab7` binary.
