---
id: pattern-proxy
type: pattern
title: Proxy
signals:
- callers repeat access checks, lazy loading or caching around the same object
- expensive or remote object accessed directly
required_evidence:
- two or more call sites wrap the same object with the same guard, cache or lazy-init logic
- the target is expensive, remote, or needs access control (cited in code)
- the target interface is stable enough to mirror
anti_signals:
- access is cheap and unrestricted
- only one call site needs the guard
- a plain cache field or lazy value inside the class suffices
precedence: ../../precedence.md
cost: 'low-medium: one stand-in class mirroring the interface'
links:
  smells:
  - smell-costly-object-access
  principles:
  - principle-srp
  - principle-ocp
  patterns:
  - pattern-decorator
---

# Proxy

**Intent.** Provide a stand-in that controls access to another object (lazy, remote, protected, caching).

**When to use.** Only when every required_evidence item can be cited from the structure model (file, symbol, line span). Per [precedence.md](../../precedence.md) P1 a smell or variation point must be cited (smell-costly-object-access).

**When NOT to use.** access is cheap and unrestricted; only one call site needs the guard; a plain cache field or lazy value inside the class suffices. Per P2 and P4, KISS and do-nothing always compete: if an anti-signal holds, keep the code as is.

**Change-safety note (P5).** Cross-cutting access rules live in one place; the real object stays unchanged.
