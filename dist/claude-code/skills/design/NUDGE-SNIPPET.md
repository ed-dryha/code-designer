# Reinforcing the design trigger (CLAUDE.md / AGENTS.md)

Copy this into your user-level or project CLAUDE.md (Claude Code) or AGENTS.md (Codex):

```
After the superpowers brainstorming spec is approved and before invoking
superpowers:writing-plans, invoke the code-designer design skill for any change
to existing code. Give the design doc it writes (docs/design/<file>) to
writing-plans as the Spec reference.
```

## Claude Code hook

Claude Code can inject the same reminder at session start. Enable it by exporting
`CODE_DESIGNER_NUDGE=1` in your shell before launching Claude Code. Setting it through
the `env` block of settings.json is unverified for now.

## Codex

Codex does not ship hooks for this plugin. It relies on the snippet above and on the
design skill description alone.
