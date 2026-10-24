---
id: pattern-mediator
type: pattern
title: Mediator
signals:
- many peer classes hold direct references to each other and call each other
- one change to a peer forces edits in several others
required_evidence:
- a cited group of 3 or more classes with mutual references (a dense call graph among peers)
- coordination logic is duplicated or scattered across those peers
- a cited past or planned change touched several peers at once
anti_signals:
- only two collaborators (a direct call is simpler)
- the mediator would itself become a god class holding all logic
- peers are coupled by data flow in one direction only
precedence: ../../precedence.md
cost: 'medium: mediator class that must be kept thin'
links:
  smells:
  - smell-tight-notification-coupling
  - smell-god-class
  principles:
  - principle-srp
  - principle-dip
  patterns:
  - pattern-observer
  - pattern-facade
---

# Mediator

**Intent.** Centralize how a set of objects interact so they no longer reference each other directly.

**When to use.** Only when every required_evidence item can be cited from the structure model (file, symbol, line span). Per [precedence.md](../../precedence.md) P1 a smell must be cited (smell-tight-notification-coupling).

**When NOT to use.** two collaborators; risk of creating a god class; one-way coupling. Per P2 and P4, KISS and do-nothing always compete: if an anti-signal holds, keep the code as is.

**Change-safety note (P5).** Peers can change without editing each other; only the mediator knows the interaction rules.
