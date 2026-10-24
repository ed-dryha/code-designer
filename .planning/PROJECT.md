# Code Designer

## What This Is

A pair of native plugins — one for Claude Code, one for Codex — that add a design stage to the superpowers brainstorm → plan workflow. Before a feature is planned, the plugin analyzes the existing codebase's structure (classes, methods, interfaces, fields), then designs how to add or change code by strictly applying GoF patterns and SOLID/KISS/DRY, so the result does not smell and later changes do not break unrelated code. It is for developers who plan features with superpowers and want design quality enforced, not hoped for.

## Core Value

Every feature plan is a pattern-justified, change-safe design grounded in evidence from the real codebase — so updating something later does not break something else.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Design stage hooks into the superpowers brainstorm → write-plan flow, so plans arrive already pattern-checked
- [ ] Structure extraction of the existing codebase (classes, methods, interfaces, fields) via a tree-sitter-backed extractor covering many languages
- [ ] Fallback to agent-driven code reading for languages without parser support, so any language works
- [ ] Feature design command: given what needs to be built + extracted structure, produces a class/interface-level design that applies GoF patterns and SOLID/KISS/DRY
- [ ] Evidence-gated pattern proposals: a pattern is proposed only when the code shows a concrete smell or variation point; otherwise the design states "no pattern, keep simple" with reasoning
- [ ] Separate code assessment command: audits existing code and reports findings (smell / violated principle, file:line evidence, impact on change-safety, suggested pattern or refactor)
- [ ] Assessment output includes a prioritized refactor backlog that can feed back into planning
- [ ] Futures agent: infers 2-4 plausible future features from the repo (code, git history, TODOs, docs), then interviews the developer to correct and extend them; the resulting variation points drive pattern proposals
- [ ] Separate future-plans command: collects the developer's future plans into a persistent, versioned roadmap file in the repo (e.g. `docs/design/future-plans.md`) that every later feature-design run reads automatically
- [ ] Two native plugins (Claude Code and Codex), each following its tool's conventions, sharing content by copy/build step

### Out of Scope

- Executing/implementing the designed code — superpowers' execute/TDD skills own implementation; this plugin stops at the design/plan
- Automated refactoring of existing code — the assessment reports and prioritizes, it does not rewrite
- Proposing a pattern for every feature regardless of fit — contradicts KISS and the evidence-gated rule
- Replacing superpowers — this plugin hooks into its planning rather than owning the whole workflow

## Context

- Target workflow is the superpowers plugin's brainstorm → write-plan flow; the design stage must slot into it with minimal friction
- Code-structure model (classes, methods, interfaces, fields) is the shared input for feature design, assessment, and futures analysis
- Tree-sitter grammars exist for most mainstream languages, which reconciles "works for any language" with "parser-backed" reliability
- Two target hosts (Claude Code plugins, Codex plugins) have different packaging/manifest conventions; content (skills, agent prompts) should be shared where possible
- Greenfield repo at `/Users/eduard_dryha/code-designer`

## Constraints

- **Distribution**: Two native plugins (Claude Code + Codex) — each tool's conventions differ; shared content is copied/built into each
- **Integration**: Must hook into superpowers planning — the value is design quality inside the workflow developers already use
- **Languages**: Any language supported — tree-sitter extractor where available, agent-reading fallback otherwise
- **Design rigor**: Pattern proposals must cite code evidence — prevents over-engineering and pattern cargo-culting
- **Persistence**: Future plans live in a versioned repo file — must be human-editable and readable by later runs

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Hook into superpowers planning (not standalone/replace) | Design quality is enforced inside the flow developers already use | — Pending |
| Two native plugins, not one shared package | Each host's conventions are respected; content shared via copy/build | — Pending |
| Evidence-gated pattern proposals | Keeps GoF/SOLID strict while honoring KISS; avoids over-engineering | — Pending |
| Tree-sitter core with agent-reading fallback | Reliable structure extraction while still supporting any language | — Pending |
| Assessment report = findings + prioritized backlog | Findings alone aren't actionable; backlog feeds back into planning | — Pending |
| Futures agent infers from repo, then interviews developer | Inference gives candidates; the developer corrects them with real roadmap knowledge | — Pending |
| Future plans persisted as a versioned repo file | Every feature design reuses them; reviewable and shareable via git | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-10-24 after initialization*
