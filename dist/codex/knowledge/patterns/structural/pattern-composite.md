---
id: pattern-composite
type: pattern
title: Composite
signals:
- code distinguishes single items from collections with instanceof or separate loops
- recursive tree structure handled by ad hoc traversal at several sites
required_evidence:
- a tree or nested structure of items, with child collection fields on the cited class
- two or more call sites branch on leaf versus group before doing the same operation
- operations that conceptually apply to both leaf and group
anti_signals:
- the structure is flat
- leaf and group have fundamentally different operations
- tree depth is fixed at 1 and will stay so
precedence: ../../precedence.md
cost: 'medium: shared component interface, can force leaf classes to implement irrelevant methods'
links:
  smells:
  - smell-uniform-treatment-gap
  principles:
  - principle-ocp
  - principle-lsp
  patterns: []
---

# Composite

**Intent.** Treat individual objects and compositions of objects through one interface.

**When to use.** Only when every required_evidence item can be cited from the structure model (file, symbol, line span). Per [precedence.md](../../precedence.md) P1 a smell or variation point must be cited (smell-uniform-treatment-gap).

**When NOT to use.** the structure is flat; leaf and group have fundamentally different operations; tree depth is fixed at 1 and will stay so. Per P2 and P4, KISS and do-nothing always compete: if an anti-signal holds, keep the code as is.

**Change-safety note (P5).** Operations on a tree are written once; adding a new node type does not touch traversal code.
