---
description: Refresh and list reviewed Fab7 extensions and installed development snapshots
allowed-tools: Bash(fab7 ext list:*)
---

Run `fab7 ext list --refresh --json` exactly once. Report the catalog version,
available extensions, installed origin, and any exact Fab7 error. Do not edit
`~/.fab7/` or fetch registry data through another tool.
