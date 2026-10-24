---
id: smell-request-coupling
type: smell
title: Request Coupling
signals: [sender hard-wired to a specific handler, request handling spread across if-chains choosing the receiver, invocation logic fused with the operation it triggers]
links:
  smells: []
  principles: [principle-dip, principle-ocp]
  patterns: []
---

# Request Coupling

**What it looks like.** Observable in structure-model facts: sender hard-wired to a specific handler; request handling spread across if-chains choosing the receiver; invocation logic fused with the operation it triggers.

**When it is NOT a smell.** A single fixed receiver.
