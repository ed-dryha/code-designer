---
id: smell-tight-notification-coupling
type: smell
title: Tight Notification Coupling
signals: [a class directly calls update methods on several concrete dependents, adding a listener requires editing the notifier]
links:
  smells: []
  principles: [principle-dip]
  patterns: []
---

# Tight Notification Coupling

**What it looks like.** Observable in structure-model facts: a class directly calls update methods on several concrete dependents; adding a listener requires editing the notifier.

**When it is NOT a smell.** A single fixed collaborator that will never change.
