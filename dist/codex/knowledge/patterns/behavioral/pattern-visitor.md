---
id: pattern-visitor
type: pattern
title: Visitor
signals:
- the same kind of operation is added to many element classes
- type checks or casts select behavior per element class
required_evidence:
- a cited stable element hierarchy of 3 or more classes
- 2 or more distinct operations scattered across the hierarchy or implemented with type checks
- history or plan shows operations are added more often than element classes
anti_signals:
- the element hierarchy changes more often than the operations
- only one operation exists
- the language offers pattern matching over sealed types that already does this
precedence: ../../precedence.md
cost: 'medium-high: visitor interface and accept method on every element'
links:
  smells:
  - smell-scattered-operations
  - smell-type-switch
  principles:
  - principle-ocp
  - principle-srp
  patterns:
  - pattern-composite
  - pattern-interpreter
---

# Visitor

**Intent.** Move operations out of an element hierarchy into visitor classes, one per operation.

**When to use.** Only when every required_evidence item can be cited from the structure model (file, symbol, line span). Per [precedence.md](../../precedence.md) P1 a smell must be cited (smell-scattered-operations or smell-type-switch).

**When NOT to use.** the element hierarchy changes more often than operations; a single operation; pattern matching available. Per P2 and P4, KISS and do-nothing always compete: if an anti-signal holds, keep the code as is.

**Change-safety note (P5).** A new operation is one new class; element classes stay untouched.
