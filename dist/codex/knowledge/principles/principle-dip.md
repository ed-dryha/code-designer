---
id: principle-dip
type: principle
title: Dependency Inversion Principle
links:
  smells: [smell-hardcoded-construction, smell-global-state, smell-incompatible-interface, smell-tight-notification-coupling, smell-request-coupling]
  principles: []
  patterns: []
---

# Dependency Inversion Principle

**Intent.** Depend on abstractions, not concrete details.

**How to detect a violation.** new of concrete classes inside business logic, static access to singletons, high-level code importing low-level modules.

**When NOT to apply.** Stable concrete dependencies (value types, standard library) that will never be swapped or faked.

**Precedence.** Applies only under P1 (cited evidence) and P2 (KISS and evidence beat speculative SOLID); see ../precedence.md.
