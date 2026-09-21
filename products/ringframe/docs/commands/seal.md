# Seal

**You decide. Seal closes every open Ask with that decision and writes a
receipt you can check later.**

`/rf:seal <decision> [note]` in Claude Code, `$rf:seal <decision> [note]` in
Codex.

Four decisions: `accepted`, `rejected`, `deferred`, `abandoned`. **All four
close the Asks**, `deferred` included — it means "not now", not "ask me later".

Seal does not merge, publish, deploy, or certify anything. It records what you
decided.

## Making the decision

The skill shows you the decision, the open Asks, a summary of the Eval if there
is one, and your note. It asks again only if your answer changes the decision
without clearly confirming it, or is ambiguous.

A note on its own is not a yes.

The CLI records what the skill reports. It cannot independently watch you click
the button.

Your note is kept word for word. By default the receipt points at the most
recent finished Eval that covers at least one of the Asks being closed, or no
Eval if there is none — and it keeps that Eval's ID so anyone reading the
receipt can go look at what it actually covered.

**A bad Eval never blocks a Seal.** Neither does an old one, one whose code has
moved on, or no Eval at all. The decision is yours; the receipt just records
what you knew when you made it.

If you are a person answering interactively, your say-so is enough. Anything
else — a script, an agent — needs a local grant file in
`authorizations/<actor>.json` matching its identity, the decision, and the kind
of subject, with an expiry if one is set. These are local grants, not real
authentication.

The [Claude skill](https://github.com/fab7hq/fab7/blob/main/products/ringframe/plugins/claude/skills/seal/SKILL.md)
asks with `AskUserQuestion`, the
[Codex skill](https://github.com/fab7hq/fab7/blob/main/products/ringframe/plugins/codex/skills/seal/SKILL.md)
with `request_user_input`. If that tool is missing, refused, cancelled, or left
unanswered, no Seal is created.

## When it refuses

| Code | What happened |
| --- | --- |
| `seal.no_open_ask` | Nothing is open to close. |
| `seal.eval_missing` | You named an Eval that is not finished, or does not exist. |
| `seal.eval_unrelated` | You named an Eval that covers none of these Asks. |
| `seal.authority_missing` | A non-human actor with no matching grant. |

A refusal is recorded too, and writes no receipt.

## The receipt

`seals/<seal_id>.json` holds the Asks and their titles, the subject at the time,
the Eval it referenced (or nothing), your decision, your note, who you were,
under what authority, the known limitations, and when. If there is an Eval, it
keeps that Eval's digest, verdict, confidence, age, and whether its subject
still matched at the moment you sealed.

Outside Git, the subject may simply be unknown, and the receipt says so.

```sh
ringframe seal create --disposition accepted --note "Reviewed locally"
ringframe seal check --seal <seal_id> --json
```

`seal check` confirms the receipt has not been altered and that the Eval it
names is the Eval it was written against. `fresh: true` and exit `0` mean both
held.

`subject_matches` is a **separate** answer: does the code it was sealed against
still hash the same? For a commit that checks *that commit* — it does not tell
you whether your current `HEAD` or working tree matches it.

Anything downstream decides for itself what a Seal is worth.
