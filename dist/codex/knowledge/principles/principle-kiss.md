---
id: principle-kiss
type: principle
title: Keep It Simple
links:
  smells: [smell-telescoping-constructor, smell-speculative-generality]
  principles: []
  patterns: []
---

# Keep It Simple

**Intent.** Prefer the simplest design that satisfies the evidenced need.

**How to detect a violation.** Abstractions with a single implementation, parameters never varied, indirection layers without a second user.

**When NOT to apply.** Never a reason to leave an evidenced smell unfixed; simplicity is judged against current evidence.

**Precedence.** Applies only under P1 (cited evidence) and P2 (KISS and evidence beat speculative SOLID); see ../precedence.md.
