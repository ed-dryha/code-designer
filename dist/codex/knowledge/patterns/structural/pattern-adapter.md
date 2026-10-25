---
id: pattern-adapter
type: pattern
title: Adapter
signals:
- third-party or legacy type used through wrappers or conversion code at many call sites
- call sites translate method names or data shapes before every call
required_evidence:
- a cited class whose interface differs from the interface callers expect, with the mismatch visible in signatures
- two or more call sites perform the same translation inline
- the incompatible class is third-party, generated, or otherwise not editable
anti_signals:
- the interface is under your control, so change it directly
- only one call site and one-line translation
- the mismatch is a wide simplification need (see facade)
precedence: ../../precedence.md
cost: 'low: one wrapper class per adaptee'
links:
  smells:
  - smell-incompatible-interface
  principles:
  - principle-dip
  - principle-ocp
  patterns:
  - pattern-facade
---

# Adapter

**Intent.** Wrap an incompatible interface so it satisfies the interface clients expect.

**When to use.** Only when every required_evidence item can be cited from the structure model (file, symbol, line span). Per [precedence.md](../../precedence.md) P1 a smell or variation point must be cited (smell-incompatible-interface).

**When NOT to use.** the interface is under your control, so change it directly; only one call site and one-line translation; the mismatch is a wide simplification need (see facade). Per P2 and P4, KISS and do-nothing always compete: if an anti-signal holds, keep the code as is.

**Change-safety note (P5).** Changes to the foreign API are absorbed in one class instead of every call site.
