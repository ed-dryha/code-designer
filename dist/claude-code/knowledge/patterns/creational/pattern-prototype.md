---
id: pattern-prototype
type: pattern
title: Prototype
signals:
- objects created by copying a configured instance
- construction is expensive and results differ only slightly
required_evidence:
- construction code that is expensive (I/O, heavy setup) shown in a constructor or init method
- two or more call sites create near-identical instances by re-running the same setup
- the exact concrete class is not known by the caller, only a template instance
anti_signals:
- construction is cheap
- instances differ substantially so copying saves nothing
- deep copying is hard because of shared mutable or external resources
precedence: ../../precedence.md
cost: 'medium: needs a correct clone/copy contract per class'
links:
  smells:
  - smell-hardcoded-construction
  - smell-costly-object-access
  principles:
  - principle-dip
  - principle-kiss
  patterns: []
---

# Prototype

**Intent.** Create new objects by cloning a configured prototype instead of rebuilding from scratch.

**When to use.** Only when every required_evidence item can be cited from the structure model (file, symbol, line span). Per [precedence.md](../../precedence.md) P1 a smell or variation point must be cited (smell-hardcoded-construction, smell-costly-object-access).

**When NOT to use.** construction is cheap; instances differ substantially so copying saves nothing; deep copying is hard because of shared mutable or external resources. Per P2 and P4, KISS and do-nothing always compete: if an anti-signal holds, keep the code as is.

**Change-safety note (P5).** Callers depend only on the clone contract, not on the setup details of the class.
