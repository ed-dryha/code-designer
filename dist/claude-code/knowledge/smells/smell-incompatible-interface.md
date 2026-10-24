---
id: smell-incompatible-interface
type: smell
title: Incompatible Interface
signals: [client calls a third-party or legacy API directly in many places, method names/signatures differ between components that must be interchangeable]
links:
  smells: []
  principles: [principle-dip, principle-isp]
  patterns: []
---

# Incompatible Interface

**What it looks like.** Observable in structure-model facts: client calls a third-party or legacy API directly in many places; method names/signatures differ between components that must be interchangeable.

**When it is NOT a smell.** A single call site using a library once.
