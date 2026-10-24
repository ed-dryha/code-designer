---
id: smell-exposed-internals
type: smell
title: Exposed Internals
signals: [public fields or getters leaking internal state, callers restore or snapshot object state by reading its internals]
links:
  smells: []
  principles: [principle-srp]
  patterns: []
---

# Exposed Internals

**What it looks like.** Observable in structure-model facts: public fields or getters leaking internal state; callers restore or snapshot object state by reading its internals.

**When it is NOT a smell.** Plain data transfer objects.
