---
id: smell-refused-bequest
type: smell
title: Refused Bequest
signals: [subclass overrides inherited methods to throw or do nothing, callers check the concrete subtype before calling]
links:
  smells: []
  principles: [principle-lsp]
  patterns: []
---

# Refused Bequest

**What it looks like.** Observable in structure-model facts: subclass overrides inherited methods to throw or do nothing; callers check the concrete subtype before calling.

**When it is NOT a smell.** Abstract hooks with intentionally empty default bodies.
