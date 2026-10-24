---
name: extract-structure
description: Use when you need a structure model of the codebase - classes, interfaces, methods, fields, symbol ids and spans - before assessing or designing a change. Produces and validates .code-designer/structure-model.json.
---

# Extract Structure

Resolve SKILL_DIR to the directory containing this SKILL.md (Codex hosts only; ignore on hosts that expand script paths directly).

Build a validated structure model of the current repository. The model is regenerable and `.code-designer/` is gitignored.

1. Ensure grammars are available:

   ```
   python3 $SKILL_DIR/scripts/cd_setup.py --cache-dir ~/.cache/code-designer --detect .
   ```

   Use `--status` to inspect the cache without downloading.

2. Extract the model:

   ```
   uv run --script $SKILL_DIR/scripts/cd_extract.py . --cache-dir ~/.cache/code-designer --out .code-designer/structure-model.json
   ```

   If `uv` is absent, run the same script with the venv python that setup created.

3. Validate the model:

   ```
   python3 $SKILL_DIR/scripts/cd_validate.py .code-designer/structure-model.json
   ```

4. If extraction exits with code 3, or the repository uses languages without a grammar, follow `FALLBACK.md` in this skill directory (agent-read path, same schema, `inferred` flags). Never hide partial coverage.
