---
id: smell-divergent-change
type: smell
title: Divergent Change
signals: [one class edited for unrelated reasons across commits, method groups tied to different concerns in the same class]
links:
  smells: []
  principles: [principle-srp, principle-ocp]
  patterns: []
---

# Divergent Change

**What it looks like.** Observable in structure-model facts: one class edited for unrelated reasons across commits; method groups tied to different concerns in the same class.

**When it is NOT a smell.** A class changing often for a single reason.
