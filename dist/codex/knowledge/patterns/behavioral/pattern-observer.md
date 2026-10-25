---
id: pattern-observer
type: pattern
title: Observer
signals:
- a subject calls several named dependents after each change
- adding a new reaction means editing the subject
required_evidence:
- a cited method that, after a state change, calls 2 or more concrete dependents by name
- a cited change history or plan that adds or removes dependents
- dependents have no need to return results to the subject
anti_signals:
- one fixed dependent that will not change
- the language or framework already provides events or signals for this
- ordering or transactional guarantees between reactions are required and hard to preserve
precedence: ../../precedence.md
cost: 'low-medium: subscription API and lifecycle management'
links:
  smells:
  - smell-tight-notification-coupling
  - smell-shotgun-surgery
  principles:
  - principle-ocp
  - principle-dip
  patterns:
  - pattern-mediator
---

# Observer

**Intent.** Let dependents subscribe to a subject so state changes notify them without the subject knowing who they are.

**When to use.** Only when every required_evidence item can be cited from the structure model (file, symbol, line span). Per [precedence.md](../../precedence.md) P1 a smell must be cited (smell-tight-notification-coupling).

**When NOT to use.** one fixed dependent; built-in event mechanism exists; strict ordering needed. Per P2 and P4, KISS and do-nothing always compete: if an anti-signal holds, keep the code as is.

**Change-safety note (P5).** Adding a reaction no longer edits the subject; subject changes cannot break unrelated listeners.
