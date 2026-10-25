#!/usr/bin/env bash
# Opt-in design-stage nudge. Silent unless CODE_DESIGNER_NUDGE=1.
# Opt-in: a shell `export CODE_DESIGNER_NUDGE=1` is guaranteed to work; setting it via
# the `env` block of Claude Code settings.json is untested for SessionStart hooks
# (assumption A1, verified in plan 02-10).
# Invoked via `bash`, so the executable bit is not required.
[ "${CODE_DESIGNER_NUDGE:-}" = "1" ] || exit 0
cat <<'EOF'
{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"When the brainstorming spec is approved and before you invoke superpowers:writing-plans, please invoke code-designer:design for any change to existing code. Hand its design doc to superpowers:writing-plans as the Spec."}}
EOF
