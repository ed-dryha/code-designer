---
id: pattern-decorator
type: pattern
title: Decorator
signals:
- subclasses exist for each combination of optional behaviors
- a subclass inherits methods it does not want just to add one behavior
required_evidence:
- subclasses or flags that combine optional responsibilities (e.g. logging, caching, validation) over the same interface
- at least 3 combinations exist or are planned
- the cited base interface is small enough to wrap
anti_signals:
- behaviors are fixed and never combined
- a single optional behavior with one call site
- the interface is large, making wrapper forwarding costly
precedence: ../../precedence.md
cost: 'medium: wrapper per behavior, forwarding boilerplate, order sensitivity'
links:
  smells:
  - smell-class-explosion
  - smell-refused-bequest
  principles:
  - principle-ocp
  - principle-srp
  patterns:
  - pattern-bridge
  - pattern-proxy
---

# Decorator

**Intent.** Add responsibilities to an object dynamically by wrapping it with objects of the same interface.

**When to use.** Only when every required_evidence item can be cited from the structure model (file, symbol, line span). Per [precedence.md](../../precedence.md) P1 a smell or variation point must be cited (smell-class-explosion, smell-refused-bequest).

**When NOT to use.** behaviors are fixed and never combined; a single optional behavior with one call site; the interface is large, making wrapper forwarding costly. Per P2 and P4, KISS and do-nothing always compete: if an anti-signal holds, keep the code as is.

**Change-safety note (P5).** A new behavior is a new wrapper; existing classes and their other combinations are untouched.
