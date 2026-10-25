# Agent-read fallback

Use this when the tree-sitter path cannot cover the repository. The result is the same schema (`structure-model.md`) with agent provenance, so downstream skills treat it identically but weigh it as inferred.

## When to enter

- `cd_extract.py` exited with exit 3 (grammars unavailable, status `partial` or `unavailable`).
- `cd_setup.py` exited with exit 3 (offline or download failed).
- Neither `uv` nor `python3` is available (reason `no-runtime`).
- The repository contains a language with no grammar or queries (`coverage.unavailable` reason `no-grammar`).

## Procedure

1. Read the model already written by `cd_extract.py` (if any) and take the files and languages listed under `coverage.unavailable`. If no model exists, list the source files yourself, skipping `.git`, `node_modules`, `vendor`, `.venv`, `dist`, `build`, files over 1 MB and symlinks that leave the root. Record each skipped path in `coverage.skipped` with its reason.
2. Read only those files. Do not read files already covered by tree-sitter.
3. For each file emit symbols (classes, interfaces, methods, constructors, functions, fields) following the id scheme and span rules in `structure-model.md`. Every symbol must have `provenance: "agent"`, `inferred: true`, `hash: null`, and an exact 1-based inclusive `span`. Never invent a symbol you did not see in the file text, and never emit a placeholder entry for a file you did not read. No silent per-file placeholders.
4. Add a `coverage.files` entry for each file you read with `provenance: "agent"`, the file's real `sha256`, `parsed: true`, the symbol count, and `hasErrors: false`. Compute it with `shasum -a 256 <file>`.
5. Merge into the tree-sitter model: remove the entries you covered from `coverage.unavailable` (drop an entry once its file list is empty; files you could not read stay listed), append your files and symbols, and set `status`: `complete` if `coverage.unavailable` is empty, otherwise `partial`. If there was no tree-sitter model, build a fresh one with `generator.source: "agent"`, `generator.pack: null`.
6. Write the result to `.code-designer/structure-model.json`.

## Mandatory validation

Run both, always, after emitting the model:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cd_validate.py .code-designer/structure-model.json --root .
```

and verify the span of every symbol you emitted with `cd_verify.py` (a citation per symbol: its file, `startLine`, `endLine`, and the first line of its signature as the quote):

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cd_verify.py --root . --citations <citations.json> --model .code-designer/structure-model.json
```

Fix every violation or failed citation before continuing. Agent-provenance symbols get no leniency from the verifier.

## Downstream rules

Anything derived from an `inferred: true` symbol is reported as inferred. It may support a finding but must not be the only evidence for a design decision (knowledge-base precedence rule P3).
