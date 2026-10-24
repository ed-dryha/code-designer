---
id: principle-ocp
type: principle
title: Open/Closed Principle
links:
  smells: [smell-divergent-change, smell-type-switch, smell-class-explosion, smell-uniform-treatment-gap, smell-request-coupling, smell-ad-hoc-rule-parsing, smell-scattered-operations]
  principles: []
  patterns: []
---

# Open/Closed Principle

**Intent.** Extend behavior by adding code, not editing existing code.

**How to detect a violation.** Switches or if-chains on a type field, the same edit repeated in many places for each new variant.

**When NOT to apply.** Variation that has never occurred and is not planned; abstracting early is speculative (P1, P2).

**Precedence.** Applies only under P1 (cited evidence) and P2 (KISS and evidence beat speculative SOLID); see ../precedence.md.
