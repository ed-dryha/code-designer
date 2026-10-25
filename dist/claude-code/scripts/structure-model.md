# Structure model (schemaVersion 1)

Agent-facing description of `structure-model.schema.json`. The JSON Schema is authoritative; `cd_validate.py` enforces it plus the semantic rules below. Use this document when you must produce a model by reading files yourself (see `extract-structure/FALLBACK.md`).

## Top level

| Field | Meaning |
|---|---|
| `schemaVersion` | Always `1`. |
| `generator` | `{name, version, pack, source}`. `source` is `tree-sitter` or `agent`. For a pure agent-read model use `source: "agent"` and `pack: null`. A model that merges parsed and agent-read files keeps `source: "tree-sitter"`; each symbol and file carries its own `provenance`. |
| `root` | `"."` (paths are relative to the scanned root). |
| `generatedAt` | UTC timestamp, e.g. `2026-10-24T12:00:00Z`. |
| `status` | `complete`: every source file is parsed. `partial`: some files are listed in `coverage.unavailable`. `unavailable`: nothing could be parsed. |
| `coverage` | See below. |
| `symbols` | Flat list; hierarchy is expressed by `parent`. |

## Symbols

- `id`: `<relpath>#<qualified.path>[(<params>)][~<n>]`. Relpath uses `/`. The qualified path is the enclosing type names joined by `.` and then the member name, for example `src/A.java#A.run`. The id contains no line numbers. Overloads append the whitespace-stripped parameter text from the signature, for example `A.run(int)`; if ids still collide add `~2`, `~3` in source order. Anonymous types use `<anon>` plus a `~n` ordinal within the enclosing symbol. Top-level functions use just the name with `kind: function`.
- `kind`: one of class, interface, enum, struct, trait, record, object, method, constructor, function, field, property.
- `name`, `file`, `parent` (id of enclosing symbol or `null`). Ids must be unique, every `parent` must resolve, the id must start with `<file>#`, and a child span must lie inside its parent span (same file).
- `span`: `{startLine, endLine}`, 1-based and inclusive, `endLine >= startLine`. These are the lines a citation will be checked against, so be exact.
- `signature`: declaration head text (no body) or `null`. `visibility`: public, protected, private, package, internal or `null`. `static`: boolean. `supertypes`: `[{relation, name}]`, where `relation` is `extends` (class/interface inheritance) or `implements` (TS/TSX `implements` clauses, Rust `impl Trait for Type`). `typeText`: field type text or `null`.
- `provenance`: `tree-sitter` or `agent`. `inferred`: must be `false` for tree-sitter and `true` for agent (the validator enforces `inferred == (provenance == "agent")`).
- `hash`: 12-hex hash of whitespace-normalized span text for tree-sitter symbols; `null` is allowed only for agent provenance.
- `heuristic` (optional, boolean): the symbol was guessed (for example Python `self.x` fields).

## Coverage

- `files[]`: `{path, language, parsed, symbols, hasErrors, sha256, provenance}` for each file that contributed symbols. `sha256` is the hex digest of the raw file bytes. `hasErrors` is true when the parser reported ERROR nodes.
- `unavailable[]`: `{language, files[], reason}` with reason `no-grammar`, `download-failed` or `no-runtime`. Every file that could not be parsed belongs here. A path appears in exactly one of files, unavailable, skipped.
- `skipped[]`: `{path, reason}` with reasons such as `ignored`, `too-large`, `symlink-escape`. A directory entry covers its subtree.
- With `--root`, the validator walks the repository and reports any recognised source file that is in none of the three lists (`coverage-missing`).

## Exit codes

| Tool | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| `cd_extract.py` | complete | n/a | usage / IO error | grammars unavailable, model still written with status partial or unavailable |
| `cd_setup.py` | all grammars ok | n/a | usage or hard failure (checksum mismatch, venv bootstrap) | at least one grammar failed (offline) |
| `cd_validate.py` | clean | violations | usage | n/a |
| `cd_verify.py` | all citations pass | any fail | usage | n/a |
