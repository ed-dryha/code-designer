---
id: smell-type-switch
type: smell
title: Type Switch
signals: [switch or if-chain on a type field or enum in several methods, each new variant requires editing every switch]
links:
  smells: []
  principles: [principle-ocp]
  patterns: []
---

# Type Switch

**What it looks like.** Observable in structure-model facts: switch or if-chain on a type field or enum in several methods; each new variant requires editing every switch.

**When it is NOT a smell.** A single switch on a closed enum that will not grow.
