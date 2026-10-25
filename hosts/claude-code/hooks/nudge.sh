#!/usr/bin/env bash
# Opt-in design-stage nudge. Silent unless CODE_DESIGNER_NUDGE=1.
# Opt-in: either a shell `export CODE_DESIGNER_NUDGE=1` or the `env` block of Claude Code
# settings.json works for SessionStart hooks (assumption A1, verified in 02-TRIGGER-CHECK).
# Invoked via `bash`, so the executable bit is not required.
[ "${CODE_DESIGNER_NUDGE:-}" = "1" ] || exit 0
cat <<'EOF'
{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"Instruction from the user's code-designer opt-in. When the brainstorming spec is approved, do not invoke superpowers:writing-plans yet, even though brainstorming names it as the next step. First invoke code-designer:design for any change to existing code and wait until its gate passes. Then invoke superpowers:writing-plans and give it the design doc (docs/design/<file>) as the Spec."}}
EOF
