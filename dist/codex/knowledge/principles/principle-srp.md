---
id: principle-srp
type: principle
title: Single Responsibility Principle
links:
  smells: [smell-god-class, smell-divergent-change, smell-shotgun-surgery, smell-costly-object-access, smell-exposed-internals]
  principles: []
  patterns: []
---

# Single Responsibility Principle

**Intent.** A class has one reason to change.

**How to detect a violation.** Class size, field clusters used by disjoint method groups, imports from unrelated domains.

**When NOT to apply.** A small cohesive class that merely has many callers; splitting it would add indirection with no change pressure (P2).

**Precedence.** Applies only under P1 (cited evidence) and P2 (KISS and evidence beat speculative SOLID); see ../precedence.md.
