---
id: pattern-command
type: pattern
title: Command
signals:
- requests are encoded as flags, strings or enums and interpreted later
- undo, queueing, retry or logging of operations is needed
required_evidence:
- a cited invoker that holds a direct reference to a concrete receiver and calls it by name at 2 or more sites
- a cited requirement or code path that queues, logs, retries or undoes operations
- operations carry parameters that must travel with them
anti_signals:
- a plain function or callback already carries the operation
- no undo, queue, log or deferred execution is needed
- one call site and one receiver
precedence: ../../precedence.md
cost: 'medium: one class per operation plus invoker'
links:
  smells:
  - smell-request-coupling
  principles:
  - principle-ocp
  - principle-srp
  patterns:
  - pattern-chain-of-responsibility
  - pattern-memento
---

# Command

**Intent.** Reify a request as an object so it can be parameterized, queued, logged or undone.

**When to use.** Only when every required_evidence item can be cited from the structure model (file, symbol, line span). Per [precedence.md](../../precedence.md) P1 a smell must be cited (smell-request-coupling).

**When NOT to use.** a first-class function already carries the operation; nothing needs undo, queueing or logging; single call site. Per P2 and P4, KISS and do-nothing always compete: if an anti-signal holds, keep the code as is.

**Change-safety note (P5).** New operations are added without editing the invoker; invoker changes cannot break receivers.
