---
id: smell-speculative-generality
type: smell
title: Speculative Generality
signals: [interface or abstract class with a single implementation, 'parameters, hooks or factories never varied', extension points with no second user]
links:
  smells: []
  principles: [principle-kiss]
  patterns: []
---

# Speculative Generality

**What it looks like.** Observable in structure-model facts: interface or abstract class with a single implementation; parameters, hooks or factories never varied; extension points with no second user.

**When it is NOT a smell.** An abstraction required by a documented, planned variation.

This is the anti-smell: when it is present, or when the proposal would create it, pattern proposals must be blocked. Per P1 a pattern needs a cited smell or variation point, and per P2 KISS outranks speculative SOLID. Recommend do-nothing (P4).
