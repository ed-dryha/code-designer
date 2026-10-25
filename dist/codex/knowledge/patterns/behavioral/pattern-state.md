---
id: pattern-state
type: pattern
title: State
signals:
- several methods of one class switch on the same status field
- behavior depends on a lifecycle the object moves through
required_evidence:
- a cited class with a state field (status, phase, mode) tested in 2 or more of its methods
- transitions between states are visible in assignments to that field
- the object changes its own state over its lifetime, not just per call
anti_signals:
- the switch is on a type tag fixed at construction (see strategy)
- fewer than 3 states or only one method depends on the state
- states and transitions are better expressed as a data table
precedence: ../../precedence.md
cost: 'medium: state interface plus one class per state'
links:
  smells:
  - smell-type-switch
  principles:
  - principle-ocp
  - principle-srp
  patterns:
  - pattern-strategy
---

# State

**Intent.** Let an object alter its behavior when its internal state changes by delegating to a state object.

**Versus Strategy.** State: behavior varies across a lifecycle and the object itself moves between states. Strategy: behavior chosen by the caller or at construction and stays fixed.

**When to use.** Only when every required_evidence item can be cited from the structure model (file, symbol, line span). Per [precedence.md](../../precedence.md) P1 a smell must be cited (smell-type-switch).

**When NOT to use.** a fixed construction-time tag (see strategy); fewer than 3 states; a table suffices. Per P2 and P4, KISS and do-nothing always compete: if an anti-signal holds, keep the code as is.

**Change-safety note (P5).** A new state is a new class; transitions are localized, so state logic cannot silently diverge across methods.
