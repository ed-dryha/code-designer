---
id: pattern-flyweight
type: pattern
title: Flyweight
signals:
- very many small objects with large identical immutable state
- memory pressure from duplicated data
required_evidence:
- a class instantiated in very large numbers (collections of thousands) with shared immutable fields, shown by call-site loops
- measured or documented memory or allocation cost
- state can be split into shared intrinsic and per-use extrinsic parts
anti_signals:
- object counts are small
- state is mostly unique or mutable
- no measured memory problem (speculative optimization, violates P2)
precedence: ../../precedence.md
cost: 'high: splits state, adds factory/cache, complicates equality'
links:
  smells:
  - smell-costly-object-access
  principles:
  - principle-kiss
  - principle-srp
  patterns: []
---

# Flyweight

**Intent.** Share fine-grained immutable state among many objects to cut memory.

**When to use.** Only when every required_evidence item can be cited from the structure model (file, symbol, line span). Per [precedence.md](../../precedence.md) P1 a smell or variation point must be cited (smell-costly-object-access).

**When NOT to use.** object counts are small; state is mostly unique or mutable; no measured memory problem (speculative optimization, violates P2). Per P2 and P4, KISS and do-nothing always compete: if an anti-signal holds, keep the code as is.

**Change-safety note (P5).** Shared state is immutable, so one holder cannot corrupt another; but the split makes code harder to follow.
