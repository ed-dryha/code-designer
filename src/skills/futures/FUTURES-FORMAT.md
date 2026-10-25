# Future plans format

File: `docs/design/future-plans.md`, committed and human-editable. A stream of YAML documents separated by `---`: one header document, then one document per plan.

```
# Code Designer future plans comment
---
schema: 1
kind: code-designer-futures
---
id: P-add-provider-1a2b3c
title: Add a second payment provider
status: inferred
confidence: medium
source:
  - type: commit
    ref: 3f9c2ab
    quote: add stripe adapter
affected:
  - src/pay/**
lastConfirmed: 2026-10-25
lastConfirmedCommit: 3f9c2ab
notes: developer answer, verbatim
```

Fields: id, title, status (inferred, confirmed, done, dropped), confidence (high, medium, low), source, affected, lastConfirmed, lastConfirmedCommit, notes. Humans may edit title, confidence, affected and notes; re-runs keep those edits.

## Input JSON (`.code-designer/futures.json`)

An object with three optional lists:

- `candidates`: at most 4 objects with `title`, `confidence`, `affected`, `source`. Never `id` or `status`; the script rejects them.
- `decisions`: objects with `id` (an existing id), `action` (confirm, edit, drop), optional `answer`, and for edit optional `title`, `confidence`, `affected`.
- `developerPlans`: plans the developer states themselves, with `title`, `confidence`, `affected`, `answer`. These are the only new plans saved as confirmed.

## Source rules

Types: commit, todo, doc, model (from candidates) and developer (script-assigned). A commit ref is a real commit hash. A todo or doc ref is `file:line` and the quote must match that line. A model ref is a symbol id from the structure model. Quotes are one line. A candidate needs at least one verified commit, todo or doc source; a model source alone is not enough.

## Affected-area rules

Repo-relative paths or `**` globs only. A symbol id reduces to its file. No `..`, no absolute paths.

## Ids

Produced by the script from the title (`cd_futures.py id --title ...`). Never typed by hand.

## Interview rules

- Ask the neutral question first, then show candidates (avoids anchoring).
- One question at a time, about 5 questions in total, "none / not sure" is valid.
- Record answers verbatim. Report "accepted all N candidates" when everything is accepted.
- `confirmed` only from an explicit developer answer.
- Always show the diff and get approval before apply.
