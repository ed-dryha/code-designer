# Code Designer

Code Designer adds a design stage to the superpowers brainstorm then plan workflow, as native plugins for Claude Code and Codex. Before a feature is planned it analyzes the existing codebase and designs the change with GoF patterns and SOLID/KISS/DRY, citing code evidence, so a later change does not break something unrelated.

## Install

The marketplace manifests are generated into the repository root by `scripts/build.py`. The repository reference below is read from `marketplace.config.json`; until the real value is set it is the placeholder `TODO-OWNER/TODO-REPO`.

### Claude Code

From the GitHub repository:

```
claude plugin marketplace add TODO-OWNER/TODO-REPO
claude plugin install code-designer@code-designer
```

Inside a session the equivalents are `/plugin marketplace add TODO-OWNER/TODO-REPO` and `/plugin install code-designer@code-designer`.

From a local clone (no GitHub identity needed), run from the clone root:

```
claude plugin marketplace add ./
claude plugin install code-designer@code-designer
```

### Codex

From the GitHub repository:

```
codex plugin marketplace add TODO-OWNER/TODO-REPO
codex plugin add code-designer@code-designer
```

From a local clone, run `codex plugin marketplace add ./` from the clone root, then the same `codex plugin add` line. The exact Codex command form has not been verified yet: check it with `codex plugin --help`. Codex caches installed plugins under `~/.codex/plugins/cache`.

## Quickstart

1. Run the extract-structure skill once in your repository. It writes `.code-designer/structure-model.json`.
2. Brainstorm the feature with superpowers and approve the spec.
3. The design skill runs next. It writes a gated design doc to `docs/design/<date>-<slug>-design.md`.
4. Hand that design doc to `superpowers:writing-plans` as the Spec.
5. Run the futures skill to create `docs/design/future-plans.md` (see below).
6. Run the assessment skill to create `docs/design/backlog.md`.

Claude Code invokes skills as `/code-designer:<skill>`; Codex invokes them as `$<skill>`.

## Trigger setup

Brainstorming names writing-plans as the next step and does not know about the design stage, so the trigger is opt-in:

- Run the `trigger-setup` skill. After you confirm, it appends an instruction snippet to `CLAUDE.md` (Claude Code) or `AGENTS.md` (Codex). The snippet text lives in `src/skills/design/NUDGE-SNIPPET.md`.
- Claude Code only: a session-start hook adds the same instruction when `CODE_DESIGNER_NUDGE=1` is set, either exported in your shell or in the `env` block of `settings.json`. It is silent otherwise.
- Codex has no hook nudge. It relies on the AGENTS.md snippet plus the design skill description.

## Skills

- `design`: evidence-gated feature design with decision records, blast radius and pattern justification; runs between brainstorming and writing-plans.
- `assessment`: finds design smells in existing code and records them in `docs/design/backlog.md`.
- `futures`: captures what is likely to change next in `docs/design/future-plans.md` after a diff and your approval; pass `--interview` to force the interview even when confirmed plans exist.
- `extract-structure`: tree-sitter structure extractor with an agent-read fallback.
- `trigger-setup`: installs the design trigger snippet.

## The future-plans file

`docs/design/future-plans.md` is committed and human-editable. Each plan has an id, title, status, confidence, sources, affected paths and notes. Statuses are `inferred`, `confirmed`, `done` and `dropped`. Only `confirmed` plans count as evidence in a design; a design doc cites one as `plan: <id>` next to a verified file citation. A confirmed plan is stale when commits have touched its affected areas since it was confirmed, and the design stage then asks whether to confirm, update, drop or skip it. Re-runs merge by id and always show a diff first.

## Requirements

- `uv` 0.9 or newer (it provides Python and the pinned tree-sitter grammar pack).
- `git` (commit sources and stale detection).
- superpowers is recommended, not required. Without it the design doc is complete but there is no Spec handoff. Code Designer never patches superpowers.

## Known limits

- On Codex the first `uv run --script` can fail in the sandbox with a uv cache write error (`Operation not permitted` under the uv cache). Retrying after allowing uv cache writes worked. Without uv, the extract-structure skill bootstraps a pinned venv with `cd_setup.py --bootstrap-venv`.
- Languages without a tree-sitter grammar use the agent-read fallback; its results are marked `inferred`.
- The Codex trigger depends on the skill description plus the AGENTS.md snippet and is not guaranteed.
- Stale detection needs git history; outside git no plan is reported stale.
