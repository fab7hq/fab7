"""RingFrame's plugin hook files and Weft's [signal] stay in step (Weft ADR-0030 D6).

For each Weft harness file with [signal]: every hook a row names is registered in
RingFrame's plugin hook file for that harness, with the row's tool as its matcher
where it names one and the row's reply as its --reply; nothing else is
registered; every entry runs the weft-signal shim with the file's id; and no
entry runs ringframe.
"""

import json
import pathlib
import shlex
import sys
import tomllib

PLUGINS = pathlib.Path("products/ringframe/plugins")
HARNESSES = pathlib.Path("products/weft/harnesses")


def hook_files():
    """Every file in RingFrame's plugins that registers hooks, and its plugin root."""
    for path in sorted(PLUGINS.rglob("*.json")):
        doc = json.loads(path.read_text())
        if path.name in ("hooks.json", "user-hooks.json"):
            yield path, doc
        elif isinstance(doc.get("capabilities"), dict) and doc["capabilities"].get("hooks"):
            yield path, doc


def entries(doc):
    """(hook, matcher, command, has_matchers) for every registered command."""
    if isinstance(doc.get("capabilities"), dict):
        for h in doc["capabilities"]["hooks"]:
            yield h["event"], None, shlex.join(h["command"]), False
        return
    for table in doc.values():
        if not isinstance(table, dict):
            continue
        for hook, listed in table.items():
            for e in listed:
                commands = [c["command"] for c in e["hooks"]] if "hooks" in e else [e["command"]]
                for command in commands:
                    yield hook, e.get("matcher"), command, True


def words_of(command):
    """A command's words, with `;`, `&&` and `>` as words of their own."""
    lex = shlex.shlex(command, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    return list(lex)


def signal_args(command):
    """(reply, id, hook) from a command that runs the shim or `weft signal`, else None."""
    words = words_of(command)
    for i, w in enumerate(words):
        if w.endswith("weft-signal") or (w == "signal" and i > 0 and words[i - 1] == "weft"):
            rest = words[i + 1 :]
            reply = None
            if rest[:1] == ["--reply"]:
                reply, rest = rest[1], rest[2:]
            if len(rest) < 2:
                return None
            return reply, rest[0], rest[1]
    return None


def same_reply(a, b):
    if a is None or b is None:
        return a == b
    try:
        return json.loads(a) == json.loads(b)
    except ValueError:
        return a == b


def check():
    bad = []
    signals = {}
    for path in sorted(HARNESSES.glob("*.toml")):
        table = tomllib.loads(path.read_text()).get("signal")
        if table is not None:
            signals[path.stem] = table
    seen = {}  # id -> [(hook, matcher, has_matchers)]
    for path, doc in hook_files():
        # Cursor's user hooks are copied into ~/.cursor by the person, away from
        # any plugin folder, so they run `weft signal` inline instead of the shim.
        root = PLUGINS / path.relative_to(PLUGINS).parts[0]
        if path.name != "user-hooks.json" and not any(root.rglob("weft-signal")):
            bad.append(f"{path}: no hooks/weft-signal shim in its plugin")
        for hook, matcher, command, has_matchers in entries(doc):
            where = f"{path}: {hook}"
            if any(w == "ringframe" or w.endswith("/ringframe") for w in words_of(command)):
                bad.append(f"{where} runs ringframe")
            args = signal_args(command)
            if args is None:
                bad.append(f"{where} does not run weft-signal: {command}")
                continue
            reply, harness, named = args
            if named != hook:
                bad.append(f"{where} names the hook {named}")
            table = signals.get(harness)
            if table is None:
                bad.append(f"{where} names {harness}, which has no harness file with [signal]")
                continue
            rows = [r for r in table.get("on", []) if r["hook"] == hook
                    and (r.get("tool") is None or not has_matchers or r.get("tool") == matcher)]
            if not rows:
                bad.append(f"{where} (matcher {matcher}) is in no [signal] row of {harness}")
                continue
            want = rows[0].get("reply", table.get("reply"))
            if not same_reply(reply, want):
                bad.append(f"{where} replies {reply!r}; [signal] says {want!r}")
            seen.setdefault(harness, []).append((hook, matcher, has_matchers))
    for harness, table in signals.items():
        for field in ("session", "workspace", "on"):
            if field not in table:
                bad.append(f"{harness}: [signal] has no {field}")
        for row in table.get("on", []):
            if row.get("forward") == "tool" and row.get("outcome") not in ("succeeded", "failed"):
                bad.append(f"{harness}: {row['hook']} forwards a tool with no outcome")
            if not any(h == row["hook"] and (row.get("tool") is None or not m_ok or m == row.get("tool"))
                       for h, m, m_ok in seen.get(harness, [])):
                bad.append(f"{harness}: [signal] row {row['hook']} {row.get('tool') or ''} is not registered")
    return bad


if __name__ == "__main__":
    problems = check()
    print("\n".join(problems) or "hooks match [signal]")
    sys.exit(1 if problems else 0)
