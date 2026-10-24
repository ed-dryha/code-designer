---
id: principle-lsp
type: principle
title: Liskov Substitution Principle
links:
  smells: [smell-refused-bequest]
  principles: []
  patterns: []
---

# Liskov Substitution Principle

**Intent.** Subtypes must be usable wherever the base type is expected.

**How to detect a violation.** Overrides that throw or no-op, subclasses narrowing preconditions, callers checking the concrete type.

**When NOT to apply.** Pure implementation inheritance in a closed hierarchy that no client uses polymorphically.

**Precedence.** Applies only under P1 (cited evidence) and P2 (KISS and evidence beat speculative SOLID); see ../precedence.md.
