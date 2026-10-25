# Backlog and findings format

## Findings JSON (input to merge)

A JSON list. Each item:

| key | meaning |
|-----|---------|
| smell | knowledge-base smell id, for example `smell-god-class` |
| principle | principle id, for example `principle-srp` |
| symbol | structure-model symbol id the finding is about |
| evidence | list of `{file, startLine, endLine, quote, symbol?}`; quote copied from the span just read |
| impact | change-safety impact: what breaks or gets risky when this code changes |
| suggestion | a pattern id or a named refactor |
| priority | `High`, `Medium` or `Low` |
| rationale | one line explaining the priority |

A finding without evidence that verifies as a real file:line (and quote) is rejected, and the whole merge writes nothing.

## Priority rubric

Priority follows change-safety impact only. Numeric scores or weighted ranking are prohibited.

- High: a change here touches many dependents or a core path.
- Medium: moderate dependents, or a contained but recurring change area.
- Low: local, rarely changed, or cosmetic.

## Backlog file

`docs/design/backlog.md` is a stream of `---` delimited YAML documents. The first is the header (`schema: 1`, `kind: code-designer-backlog`). Each following document is one finding with keys: `id`, `smell`, `principle`, `symbol`, `evidence`, `impact`, `suggestion`, `priority`, `rationale`, `status` (`open` or `resolved`), `firstSeen`, `lastSeen`, `resolvedOn`, `notes`.

IDs come only from `cd_backlog.py id --smell S --symbol ID` (the merge does this for you). Never write or edit an id by hand.

## Merge semantics

- Findings that match an existing id are updated; new ones are added.
- Findings no longer reproduced are marked `resolved`, not deleted.
- A scoped run (`--scope GLOB`) resolves only findings whose files are in scope.
- Human-edited `priority`, `rationale` and `notes` are preserved across runs.
