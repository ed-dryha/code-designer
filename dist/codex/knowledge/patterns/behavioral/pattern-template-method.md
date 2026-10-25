---
id: pattern-template-method
type: pattern
title: Template Method
signals:
- two or more classes implement the same sequence of steps with a few steps differing
- copied method bodies that diverge in the middle
required_evidence:
- a cited pair of methods in different classes with the same step order and 70 percent or more identical structure
- the differing steps are isolatable into separate methods
- the classes already share, or can sensibly share, a base class
anti_signals:
- sequences differ in order or step count, not just in step content
- no common base exists and inheritance would be forced (prefer strategy)
- duplication is one small block (tolerate it)
precedence: ../../precedence.md
cost: 'low: base method plus overridable steps'
links:
  smells:
  - smell-duplicate-code
  principles:
  - principle-dry
  - principle-ocp
  patterns:
  - pattern-strategy
  - pattern-factory-method
---

# Template Method

**Intent.** Define an algorithm's skeleton in a base class and let subclasses override specific steps.

**When to use.** Only when every required_evidence item can be cited from the structure model (file, symbol, line span). Per [precedence.md](../../precedence.md) P1 a smell must be cited (smell-duplicate-code).

**When NOT to use.** step order varies; inheritance would be forced (prefer strategy); trivial duplication. Per P2 and P4, KISS and do-nothing always compete: if an anti-signal holds, keep the code as is.

**Change-safety note (P5).** The shared sequence is fixed in one place; fixing it cannot leave one copy behind.
