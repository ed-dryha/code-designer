---
id: principle-dry
type: principle
title: Don't Repeat Yourself
links:
  smells: [smell-shotgun-surgery, smell-class-explosion, smell-duplicate-code]
  principles: []
  patterns: []
---

# Don't Repeat Yourself

**Intent.** Each piece of knowledge has one authoritative place.

**How to detect a violation.** Near-identical method bodies, the same rule encoded in several classes, parallel edits in every commit.

**When NOT to apply.** Coincidental similarity: code that looks alike but changes for different reasons should stay separate.

**Precedence.** Applies only under P1 (cited evidence) and P2 (KISS and evidence beat speculative SOLID); see ../precedence.md.
