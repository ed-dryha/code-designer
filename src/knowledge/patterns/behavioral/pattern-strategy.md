---
id: pattern-strategy
type: pattern
title: Strategy
signals:
- a switch or if chain on a type tag selects an algorithm
- the same selection logic is repeated in several places
required_evidence:
- a cited type/kind switch with 3 or more branches repeated at 2 or more call sites
- the tag is fixed per caller or at construction, not changed by the object over its life
- branches compute the same result through different algorithms
anti_signals:
- only 2 branches that rarely change
- a single call site (a local conditional is simpler)
- the tag changes as the object moves through a lifecycle (see state)
- a function parameter or lambda already carries the algorithm
precedence: ../../precedence.md
cost: 'low-medium: strategy interface plus one class or function per algorithm'
links:
  smells:
  - smell-type-switch
  - smell-duplicate-code
  - smell-divergent-change
  - smell-refused-bequest
  principles:
  - principle-ocp
  - principle-dip
  patterns:
  - pattern-state
  - pattern-template-method
---

# Strategy

**Intent.** Encapsulate interchangeable algorithms behind one interface so callers choose them without conditionals.

**Versus State.** Strategy: a type switch with 2+ call sites, tag fixed per caller. State: behavior depends on a lifecycle the object changes itself.

**When to use.** Only when every required_evidence item can be cited from the structure model (file, symbol, line span). Per [precedence.md](../../precedence.md) P1 a smell must be cited (smell-type-switch).

**When NOT to use.** two stable branches; one call site; lifecycle-driven (see state); a lambda is enough. Per P2 and P4, KISS and do-nothing always compete: if an anti-signal holds, keep the code as is.

**Change-safety note (P5).** A new algorithm is added without editing existing ones or every switch site.
