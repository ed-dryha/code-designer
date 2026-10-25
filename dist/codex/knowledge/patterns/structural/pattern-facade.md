---
id: pattern-facade
type: pattern
title: Facade
signals:
- clients call the same sequence of several subsystem classes
- clients depend on many subsystem types
required_evidence:
- two or more call sites invoke the same ordered sequence across 3+ subsystem classes
- client files import many internals of one subsystem
- subsystem internals change more often than the entry points
anti_signals:
- wrapping a single class with no simplification
- the subsystem has one entry point already
- clients need fine-grained access to the internals
precedence: ../../precedence.md
cost: 'low: one class, but it can grow into a god class'
links:
  smells:
  - smell-shotgun-surgery
  - smell-fat-interface
  principles:
  - principle-isp
  - principle-dip
  patterns:
  - pattern-adapter
---

# Facade

**Intent.** Provide a simplified entry point to a complex subsystem.

**When to use.** Only when every required_evidence item can be cited from the structure model (file, symbol, line span). Per [precedence.md](../../precedence.md) P1 a smell or variation point must be cited (smell-shotgun-surgery, smell-fat-interface).

**When NOT to use.** wrapping a single class with no simplification; the subsystem has one entry point already; clients need fine-grained access to the internals. Per P2 and P4, KISS and do-nothing always compete: if an anti-signal holds, keep the code as is.

**Change-safety note (P5).** Subsystem refactors touch the facade, not every client. Keep the facade thin (precedence.md P2).
