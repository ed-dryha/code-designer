# Knowledge Base

Static Markdown loaded by the design skills. Content is authored from general GoF/SOLID/refactoring knowledge and is maintainer-reviewed; it is not verifiable by tooling.

## Layout

- `precedence.md` - numbered rules P1-P5, loaded first (not linted as an entry)
- `principles/principle-*.md` - SOLID, KISS, DRY
- `smells/smell-*.md` - code smells visible in the structure model
- `patterns/pattern-*.md` - the 23 GoF patterns

## Frontmatter contract

All entries: `id` (equals the file name stem), `type` (smell | principle | pattern), `title`, `links` with `smells`, `principles`, `patterns` id lists.
Smells add `signals`. Patterns add `signals`, `required_evidence` (non-empty), `anti_signals` (non-empty), `precedence` (relative path to precedence.md) and `cost`.

## Ids

`principle-*`, `smell-*`, `pattern-*`. Graph: smell -> principle -> pattern. Every smell links a principle; every pattern is reachable from a smell or principle.

Check with `python3 scripts/lint_kb.py src/knowledge`.
