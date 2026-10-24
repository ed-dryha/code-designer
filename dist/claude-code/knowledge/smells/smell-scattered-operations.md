---
id: smell-scattered-operations
type: smell
title: Scattered Operations
signals: [operations over a class hierarchy implemented as instanceof chains, adding an operation means editing every class in the hierarchy]
links:
  smells: []
  principles: [principle-ocp]
  patterns: []
---

# Scattered Operations

**What it looks like.** Observable in structure-model facts: operations over a class hierarchy implemented as instanceof chains; adding an operation means editing every class in the hierarchy.

**When it is NOT a smell.** A hierarchy with a single operation.
