"""Each Weft harness file's [eval.default] is its plugin's judges' own effort.

Settings shows a judge's default effort from the harness file. The effort that
runs is the one in RingFrame's plugin agent file for that judge (rf-map,
rf-reduce, rf-confirm). A plugin is the harness's whose hooks run
`weft-signal <id>`.
"""

import json
import pathlib
import re
import sys
import tomllib

PLUGINS = pathlib.Path("products/ringframe/plugins")
HARNESSES = pathlib.Path("products/weft/harnesses")
ROLES = ("map", "reduce", "confirm")


def plugin_roots(plugins):
    """{harness id: plugin folder}, from the id each plugin's hooks name."""
    roots = {}
    for path in sorted(plugins.rglob("hooks.json")):
        root = path.parent.parent if path.parent.name == "hooks" else path.parent
        ids = set(re.findall(r"weft-signal(?: --reply '[^']*')? (\S+) ", path.read_text()))
        for harness in ids:
            roots[harness] = root
    return roots


def agent_effort(root, role):
    """The `effort:` in a judge's frontmatter, or None."""
    for path in (root / "agents" / f"rf-{role}.md", root / "agents" / f"rf-{role}" / "agent.md"):
        if path.is_file():
            front = path.read_text().split("---")[1]
            found = re.search(r"^effort:\s*(\S+)", front, re.M)
            return found.group(1) if found else None
    return None


def check(plugins=PLUGINS, harnesses=HARNESSES):
    bad = []
    roots = plugin_roots(plugins)
    for path in sorted(harnesses.glob("*.toml")):
        default = tomllib.loads(path.read_text()).get("eval", {}).get("default")
        if default is None:
            continue
        root = roots.get(path.stem)
        if root is None:
            bad.append(f"{path}: no plugin's hooks name {path.stem}")
            continue
        for role in ROLES:
            want = agent_effort(root, role)
            if default.get(role) != want:
                bad.append(f"{path}: [eval.default] {role} is {default.get(role)!r}, "
                           f"its plugin's rf-{role} runs at {want!r}")
    return bad


if __name__ == "__main__":
    found = check()
    print("\n".join(found) or "eval defaults match the plugins' judges")
    sys.exit(1 if found else 0)
