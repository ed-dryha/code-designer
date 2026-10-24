---
id: smell-global-state
type: smell
title: Global State
signals: [static mutable fields, static getInstance-style access from many classes]
links:
  smells: []
  principles: [principle-dip]
  patterns: []
---

# Global State

**What it looks like.** Observable in structure-model facts: static mutable fields; static getInstance-style access from many classes.

**When it is NOT a smell.** Immutable constants and pure static helpers.
