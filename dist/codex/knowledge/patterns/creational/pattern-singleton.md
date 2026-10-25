---
id: pattern-singleton
type: pattern
title: Singleton
signals:
- a global or static accessor to a single mutable instance
- hidden dependency reached from many classes
required_evidence:
- a resource that must exist exactly once, such as a process-wide handle, evidenced by code citing a hard single-instance constraint (file:line)
- dependency injection of the single instance is not feasible at the cited call sites
- the instance is effectively immutable or its state is guarded
anti_signals:
- it exists only for convenient global access
- tests or callers need to substitute it
- the instance holds mutable state shared across unrelated classes
- passing the object as a parameter or composition-root wiring works
precedence: ../../precedence.md
cost: 'high: global state, hidden coupling, test friction'
links:
  smells:
  - smell-global-state
  principles:
  - principle-dip
  - principle-kiss
  patterns: []
---

# Singleton

**Intent.** Ensure one instance with global access. Usually the problem rather than the fix.

**When to use.** Only when every required_evidence item can be cited from the structure model (file, symbol, line span). Per [precedence.md](../../precedence.md) P1 a smell or variation point must be cited (smell-global-state).

**When NOT to use.** it exists only for convenient global access; tests or callers need to substitute it; the instance holds mutable state shared across unrelated classes; passing the object as a parameter or composition-root wiring works. Per P2 and P4, KISS and do-nothing always compete: if an anti-signal holds, keep the code as is.

**Change-safety note (P5).** Mostly negative: a singleton lets unrelated code change each other's state. The anti-signals dominate; prefer injecting a single instance from the composition root. Per precedence.md P2, KISS wins.
