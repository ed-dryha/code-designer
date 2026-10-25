# Query capture contract

Every `queries/<lang>.scm` uses only these captures; `cd_extract.py` adapts matches
(`QueryCursor.matches`) to schema symbols.

| Capture | Meaning |
|---|---|
| `@type.<kind>` + `@type.name` | Type declaration; `<kind>` is one of class interface enum struct trait record object |
| `@type.supers` (optional) | Node whose named children are supertype names (relation `extends`) |
| `@type.impls` (optional) | Node whose named children are implemented interface names (relation `implements`) |
| `@method` + `@method.name` | Method |
| `@constructor` + `@constructor.name` | Constructor |
| `@function` + `@function.name` | Top-level function |
| `@field` + `@field.name` | Field; optional `@field.type` for declared type text |
| `@modifiers` (optional) | Node whose text holds visibility/static keywords |

Parent/child nesting is derived from byte-range containment of type nodes, never from queries.
Per-language tweaks live in `lang_hooks/<lang>.py` (`post_process(symbols, root_node, source_bytes)`).
Each raw symbol is a dict with `kind, name, node` (plus optional `supers, typeText, heuristic, modifiers`).
