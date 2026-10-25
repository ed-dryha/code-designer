---
id: pattern-chain-of-responsibility
type: pattern
title: Chain of Responsibility
signals:
- a sender must know which concrete handler processes a request
- an if/else cascade tries handlers in order until one accepts
required_evidence:
- a cited dispatch site that tests several conditions in sequence to pick a handler, with 3 or more branches
- the set or order of handlers is changed in more than one place or is expected to change
- handlers share one request type so they can be linked without adaptation
anti_signals:
- fewer than 3 handlers and the order never changes
- exactly one handler always applies (use a direct call or lookup)
- every handler must run regardless of earlier outcomes (see observer)
precedence: ../../precedence.md
cost: 'medium: handler interface plus linking code'
links:
  smells:
  - smell-request-coupling
  - smell-type-switch
  principles:
  - principle-ocp
  - principle-srp
  patterns:
  - pattern-command
---

# Chain of Responsibility

**Intent.** Pass a request along a chain of handlers until one handles it, decoupling sender from receiver.

**When to use.** Only when every required_evidence item can be cited from the structure model (file, symbol, line span). Per [precedence.md](../../precedence.md) P1 a smell must be cited (smell-request-coupling or smell-type-switch).

**When NOT to use.** fewer than 3 handlers and a fixed order; a single handler always applies; every handler must run (see observer). Per P2 and P4, KISS and do-nothing always compete: if an anti-signal holds, keep the code as is.

**Change-safety note (P5).** Adding or reordering a handler no longer edits the sender or sibling handlers.
