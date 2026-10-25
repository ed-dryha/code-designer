---
id: pattern-memento
type: pattern
title: Memento
signals:
- state is copied out field by field through public getters/setters to support undo or rollback
- snapshot and restore code lives outside the owning class
required_evidence:
- a cited class with private state whose fields are made public or copied by 2 or more external call sites to save/restore
- a cited undo, rollback or checkpoint requirement
- restore must not require callers to know the field layout
anti_signals:
- state is a small immutable value that can simply be kept
- no undo, rollback or checkpoint is needed
- a persistence layer already serializes the state
precedence: ../../precedence.md
cost: 'low-medium: snapshot class and save/restore methods'
links:
  smells:
  - smell-exposed-internals
  principles:
  - principle-srp
  patterns:
  - pattern-command
---

# Memento

**Intent.** Capture and externalize an object's state so it can be restored later without breaking encapsulation.

**When to use.** Only when every required_evidence item can be cited from the structure model (file, symbol, line span). Per [precedence.md](../../precedence.md) P1 a smell must be cited (smell-exposed-internals).

**When NOT to use.** small immutable values; no undo needed; existing serialization. Per P2 and P4, KISS and do-nothing always compete: if an anti-signal holds, keep the code as is.

**Change-safety note (P5).** Fields of the originator can change without breaking external save/restore code.
