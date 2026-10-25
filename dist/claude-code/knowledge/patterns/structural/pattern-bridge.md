---
id: pattern-bridge
type: pattern
title: Bridge
signals:
- subclass names combine two independent axes (e.g. ShapeColor)
- adding one variant on an axis forces N new subclasses
required_evidence:
- a class hierarchy whose subclasses are the cross product of two orthogonal dimensions, listed from the structure model
- at least 2x2 combinations exist or are planned
- both dimensions have changed or are planned to change independently
anti_signals:
- only one dimension varies
- dimensions are not independent
- fewer than 4 combinations and no growth planned
precedence: ../../precedence.md
cost: 'medium: two hierarchies plus a delegation field'
links:
  smells:
  - smell-class-explosion
  principles:
  - principle-ocp
  - principle-srp
  patterns:
  - pattern-decorator
---

# Bridge

**Intent.** Split an abstraction and its implementation into separate hierarchies connected by composition.

**When to use.** Only when every required_evidence item can be cited from the structure model (file, symbol, line span). Per [precedence.md](../../precedence.md) P1 a smell or variation point must be cited (smell-class-explosion).

**When NOT to use.** only one dimension varies; dimensions are not independent; fewer than 4 combinations and no growth planned. Per P2 and P4, KISS and do-nothing always compete: if an anti-signal holds, keep the code as is.

**Change-safety note (P5).** Each axis can change on its own; a new implementor cannot break abstraction subclasses.
