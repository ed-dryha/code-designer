---
id: smell-costly-object-access
type: smell
title: Costly Object Access
signals: ['callers perform expensive setup, remote or lazy access inline', 'access control, caching or lazy loading mixed into the domain class']
links:
  smells: []
  principles: [principle-srp]
  patterns: []
---

# Costly Object Access

**What it looks like.** Observable in structure-model facts: callers perform expensive setup, remote or lazy access inline; access control, caching or lazy loading mixed into the domain class.

**When it is NOT a smell.** Cheap in-memory objects.
