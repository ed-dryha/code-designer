---
name: extract-structure
description: Use when you need a structure model of the codebase - classes, interfaces, methods, fields, symbol ids and spans - before assessing or designing a change. Produces and validates .code-designer/structure-model.json.
---

# Extract Structure

Resolve SKILL_DIR to the directory containing this SKILL.md (Codex hosts only; ignore on hosts that expand script paths directly).

Build a validated structure model of the current repository. The model is regenerable and `.code-designer/` is gitignored.

1. Ensure grammars are available:

   ```
   uv run --script {{SCRIPTS}}/cd_setup.py --cache-dir {{CACHE_DIR}} --detect .
   ```

   If `uv` is not installed, run `python3 {{SCRIPTS}}/cd_setup.py --cache-dir {{CACHE_DIR}} --bootstrap-venv` once. It creates the pinned venv in the cache dir and prints its python; rerun cd_setup with `--detect .` using that python. On a cold grammar cache cd_extract exits 3 unless `--allow-download` is passed; the exit-3 handling below covers that case.

   Use `--status` to inspect the cache without downloading.

2. Extract the model:

   ```
   uv run --script {{SCRIPTS}}/cd_extract.py . --cache-dir {{CACHE_DIR}} --out .code-designer/structure-model.json
   ```

   If `uv` is absent, run the same script with the venv python that setup created.

3. Validate the model:

   ```
   python3 {{SCRIPTS}}/cd_validate.py .code-designer/structure-model.json
   ```

4. If extraction exits with code 3, or the repository uses languages without a grammar, follow `FALLBACK.md` in this skill directory (agent-read path, same schema, `inferred` flags). Never hide partial coverage.
