# Reinforcing the design trigger (CLAUDE.md / AGENTS.md)

Copy this into your user-level or project CLAUDE.md (Claude Code) or AGENTS.md (Codex):

```
When the superpowers brainstorming spec is approved, do not invoke
superpowers:writing-plans yet, even though brainstorming names it as the next step.
First invoke code-designer:design for any change to existing code and wait until
its gate passes. Then invoke superpowers:writing-plans and give it the design doc
(docs/design/<file>) as the Spec.
```

## One-step install

Run the `trigger-setup` skill (Claude Code `/code-designer:trigger-setup`, Codex
`$trigger-setup`). It appends the snippet above to your CLAUDE.md or AGENTS.md after
you confirm, and does nothing if it is already installed.

## Claude Code hook (opt-in)

Claude Code can inject the same instruction at session start. The hook is silent unless
`CODE_DESIGNER_NUDGE=1` is set. Either export it in your shell before launching Claude
Code, or use the settings.json `env` route, which was verified (plan 02-10,
02-TRIGGER-CHECK):

```json
{
  "env": {
    "CODE_DESIGNER_NUDGE": "1"
  }
}
```

## Codex

Codex does not ship hooks for this plugin. It relies on the snippet in AGENTS.md plus
the design skill description. Codex ignores `disable-model-invocation`, so the
trigger-setup skill also ships `agents/openai.yaml` with
`allow_implicit_invocation: false`; its description wording and the confirm step remain
the safeguards.
