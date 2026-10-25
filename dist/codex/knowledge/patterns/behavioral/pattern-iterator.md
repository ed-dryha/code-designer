---
id: pattern-iterator
type: pattern
title: Iterator
signals:
- callers index into or reach through a collection's internal fields to traverse it
- several traversal orders are reimplemented by clients
required_evidence:
- a cited collection class whose internal storage (array, node links) is read directly by 2 or more external call sites
- clients depend on the storage layout to traverse
- more than one traversal order exists or is planned
anti_signals:
- the language provides a native iterator or generator over the storage already
- the collection is a plain array or list with one traversal
- traversal happens in one place only
precedence: ../../precedence.md
cost: 'low: iterator class or generator method'
links:
  smells:
  - smell-exposed-internals
  principles:
  - principle-srp
  - principle-dip
  patterns:
  - pattern-composite
  - pattern-visitor
---

# Iterator

**Intent.** Provide sequential access to an aggregate without exposing its representation.

**When to use.** Only when every required_evidence item can be cited from the structure model (file, symbol, line span). Per [precedence.md](../../precedence.md) P1 a smell must be cited (smell-exposed-internals).

**When NOT to use.** the language already gives iterators or generators; one plain list with one traversal; single traversal site. Per P2 and P4, KISS and do-nothing always compete: if an anti-signal holds, keep the code as is.

**Change-safety note (P5).** Storage layout can change without breaking any traversing client.
